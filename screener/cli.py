"""Command-line entry point for the Mega-Cap Options Quantitative Edge Screener."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from rich.console import Console
from rich.table import Table

from screener.analytics import run_screen
from screener.exporter import export_to_csv, generate_html_dashboard
from screener.universe import DEFAULT_UNIVERSE, StockTicker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="5-Pillar Quantitative Mega-Cap Options Screener (Volatility Edge, Greeks, Event Risk, Fundamentals, Technicals)."
    )
    parser.add_argument(
        "--dte",
        type=int,
        default=30,
        help="Target Days-to-Expiration (DTE) for option chain selection (default: 30)",
    )
    parser.add_argument(
        "--otm",
        type=float,
        default=0.05,
        help="Target Out-of-the-Money (OTM) fraction from spot price, e.g. 0.05 for 5%% OTM (default: 0.05)",
    )
    parser.add_argument(
        "--delta",
        type=float,
        default=None,
        help="Optional target absolute Black-Scholes Delta (e.g. 0.20 for ~80%% PoP) instead of fixed OTM %%",
    )
    parser.add_argument(
        "--min-pe",
        type=float,
        default=0.0,
        help="Minimum P/E ratio filter (strictly greater than this value, default: 0.0)",
    )
    parser.add_argument(
        "--region",
        choices=["ALL", "US", "EU"],
        default="ALL",
        help="Filter stock universe by region (default: ALL)",
    )
    parser.add_argument(
        "--tickers",
        nargs="*",
        help="Optional custom ticker symbols to screen instead of the default universe",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default="output/megacap_options_yields.csv",
        help="Output CSV file path (default: output/megacap_options_yields.csv)",
    )
    parser.add_argument(
        "--html",
        type=str,
        default="output/dashboard.html",
        help="Output interactive HTML dashboard path (default: output/dashboard.html)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser.parse_args()


def print_rich_table(df, console: Console) -> None:
    if df.empty:
        console.print("[yellow]No tickers matched the screening criteria.[/yellow]")
        return

    table = Table(title="Mega-Cap Options Quantitative Edge Screener (P/E > 0)", show_lines=False)
    table.add_column("Ticker", style="bold cyan")
    table.add_column("Reg", style="magenta")
    table.add_column("Spot", justify="right")
    table.add_column("P/E", justify="right")
    table.add_column("RSI", justify="right")
    table.add_column("HV30", justify="right")
    table.add_column("Opt IV", justify="right")
    table.add_column("VRP", justify="right")
    table.add_column("CSP Strike (Delta)", justify="right")
    table.add_column("CSP PoP", justify="right")
    table.add_column("CSP Yield", justify="right", style="bold green")
    table.add_column("CC+Div Yield", justify="right", style="bold yellow")
    table.add_column("Edge", justify="right", style="bold bright_white")
    table.add_column("Action Signal", justify="left")

    for _, row in df.iterrows():
        vrp_val = float(row["vrp_pct"])
        vrp_str = f"{vrp_val:+.1f}%"
        earn_flag = " [EARN!]" if row["earnings_before_expiry"] else ""
        table.add_row(
            str(row["symbol"]),
            str(row["region"]),
            f"${row['spot_price']:.2f}",
            f"{row['trailing_pe']:.1f}x",
            f"{row['rsi_14']:.0f}",
            f"{row['hv_30d_pct']:.1f}%",
            f"{row['csp_iv_pct']:.1f}%",
            vrp_str,
            f"${row['csp_strike']:.1f} ({row['csp_delta']:.2f})",
            f"{row['csp_pop_pct']:.0f}%",
            f"{row['csp_annualized_yield_pct']:.2f}%",
            f"{row['cc_total_income_yield_pct']:.2f}%",
            f"{row['edge_score']:.1f}",
            f"{row['strategy_signal']}{earn_flag}",
        )

    console.print(table)


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.ERROR,
        format="%(levelname)s: %(message)s",
    )
    console = Console(width=155)

    if args.tickers:
        universe = [
            StockTicker(symbol=t.upper(), name=t.upper(), region="CUSTOM", country="N/A")
            for t in args.tickers
        ]
    else:
        universe = [
            t for t in DEFAULT_UNIVERSE if args.region == "ALL" or t.region == args.region
        ]

    mode_str = f"Target Delta: {args.delta}" if args.delta else f"Target OTM: {args.otm * 100:.1f}%"
    console.print(
        f"[bold blue]Screening {len(universe)} Mega-Cap stocks across 5 Quantitative Pillars[/bold blue] "
        f"(Filter: P/E > {args.min_pe}, Target DTE: {args.dte}d, {mode_str})..."
    )

    df = run_screen(
        universe=universe,
        target_dte=args.dte,
        target_otm_pct=args.otm,
        target_delta=args.delta,
        min_pe=args.min_pe,
    )

    print_rich_table(df, console)

    if not df.empty:
        csv_path = export_to_csv(df, Path(args.csv))
        html_path = generate_html_dashboard(
            df,
            Path(args.html),
            target_dte=args.dte,
            target_otm_pct=args.otm,
        )
        console.print(f"\n[green][OK] CSV exported to:[/green] {csv_path.resolve()}")
        console.print(f"[green][OK] HTML Dashboard exported to:[/green] {html_path.resolve()}")


if __name__ == "__main__":
    main()
