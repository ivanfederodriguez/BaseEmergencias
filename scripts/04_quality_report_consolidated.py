"""
Genera un reporte de calidad sobre la tabla consolidada por evento.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from importlib.machinery import SourceFileLoader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data_clean" / "emergencias_productores_consolidated.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data_intermediate" / "reporte_calidad_consolidated.xlsx"
QUALITY_MODULE = PROJECT_ROOT / "scripts" / "02_quality_report.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generar reporte de calidad de la tabla consolidada.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    module = SourceFileLoader("quality_report_base", str(QUALITY_MODULE)).load_module()
    sheets = module.build_quality_report(args.input, args.output)
    print(f"Reporte de calidad consolidado generado: {args.output}")
    for sheet_name, sheet_df in sheets.items():
        print(f"{sheet_name}: {len(sheet_df)} filas")


if __name__ == "__main__":
    main()
