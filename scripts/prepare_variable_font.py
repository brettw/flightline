"""Prepare an exported Flightline variable TTF for distribution."""

from io import BytesIO
from pathlib import Path


def prepare_font(data, ttlib):
    # Use a separate reader to inspect glyphs. If already unhinted, preserve the
    # original glyf and loca bytes rather than recompiling every outline.
    with ttlib.TTFont(BytesIO(data)) as probe:
        if not all(tag in probe for tag in ("glyf", "fvar", "gvar")):
            raise ValueError("Expected a variable TrueType font")
        glyf = probe["glyf"]
        has_hints = any(getattr(glyf[name], "program", None) for name in probe.getGlyphOrder())

    with ttlib.TTFont(BytesIO(data), recalcBBoxes=False, recalcTimestamp=False) as font:
        if has_hints:
            font["glyf"].removeHinting()
        for tag in ("fpgm", "cvt ", "cvar", "hdmx", "LTSH", "VDMX"):
            if tag in font:
                del font[tag]
        font["head"].flags &= ~((1 << 2) | (1 << 4))

        # Match gftools.fix.fix_unhinted_font: one all-size range, and smart
        # dropout control including stubs. No instruction moves outline points.
        gasp = font["gasp"] = ttlib.newTable("gasp")
        gasp.version = 1
        gasp.gaspRange = {0xFFFF: 0x000F}
        prep = font["prep"] = ttlib.newTable("prep")
        # PUSHW 0x01FF; SCANCTRL; PUSHB 4; SCANTYPE.
        prep.decompile(bytes.fromhex("B8 01 FF 85 B0 04 8D"), font)

        maxp = font["maxp"]
        maxp.maxZones = 1
        maxp.maxStackElements = 1  # Each SCAN instruction consumes its argument.
        maxp.maxTwilightPoints = maxp.maxStorage = 0
        maxp.maxFunctionDefs = maxp.maxInstructionDefs = maxp.maxSizeOfInstructions = 0
        result = BytesIO()
        font.save(result)
        return result.getvalue()


if __name__ == "__main__":
    import argparse
    from fontTools import ttLib

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="FontLab variable TTF export")
    parser.add_argument("output", type=Path, help="destination for the unhinted TTF")
    args = parser.parse_args()
    args.output.write_bytes(prepare_font(args.source.read_bytes(), ttLib))
