"""Convert HTA PlotSpec objects to Plotly JSON dicts."""

from __future__ import annotations

from typing import Any


PLOTLY_PALETTE = ["#4f46e5", "#94a3b8", "#10b981", "#f59e0b", "#ef4444"]
BASE_LAYOUT: dict[str, Any] = {
    "plot_bgcolor": "#f8fafc",
    "paper_bgcolor": "#ffffff",
    "margin": {"t": 20, "r": 20, "b": 50, "l": 55},
    "height": 340,
    "showlegend": True,
    "font": {"family": "Inter, system-ui, sans-serif", "size": 12, "color": "#475569"},
}


def plotspec_to_plotly(spec: dict[str, Any]) -> dict[str, Any]:
    """Convert a PlotSpec dict to a Plotly-compatible {data, layout} dict."""
    plot_type = spec.get("plot_type", "")
    data_raw: dict[str, Any] = spec.get("data", {})
    title = spec.get("title", "")
    x_label = spec.get("x_label", "")
    y_label = spec.get("y_label", "")

    layout: dict[str, Any] = {
        **BASE_LAYOUT,
        "xaxis": {"title": x_label},
        "yaxis": {"title": y_label},
        "title": {"text": title, "font": {"size": 13}},
    }

    if plot_type == "boxplot":
        traces = []
        for i, (group, values) in enumerate(data_raw.items()):
            traces.append({
                "type": "box",
                "name": group,
                "y": values,
                "marker": {"color": PLOTLY_PALETTE[i % len(PLOTLY_PALETTE)]},
                "boxmean": True,
            })
        return {"data": traces, "layout": layout}

    if plot_type == "histogram":
        traces = []
        for i, (group, values) in enumerate(data_raw.items()):
            traces.append({
                "type": "histogram",
                "name": group,
                "x": values,
                "opacity": 0.7,
                "marker": {"color": PLOTLY_PALETTE[i % len(PLOTLY_PALETTE)]},
            })
        layout["barmode"] = "overlay"
        return {"data": traces, "layout": layout}

    if plot_type == "scatter":
        return {
            "data": [{
                "type": "scatter",
                "mode": "markers",
                "x": data_raw.get("x", []),
                "y": data_raw.get("y", []),
                "marker": {"color": PLOTLY_PALETTE[0], "opacity": 0.7},
            }],
            "layout": layout,
        }

    if plot_type == "heatmap":
        # Geographic / 2-D density field. `z` is a 2-D array of values; `x` and `y`
        # are the (optional) bin-center coordinates. Used for the clinic-density
        # heatmap (clinics per 100k across a lat/long grid).
        heat_layout = {**layout}
        # Keep geographic aspect roughly square so the map isn't badly distorted.
        heat_layout["yaxis"] = {**heat_layout.get("yaxis", {}), "scaleanchor": "x"}
        heat_layout["showlegend"] = False
        return {
            "data": [{
                "type": "heatmap",
                "x": data_raw.get("x", []),
                "y": data_raw.get("y", []),
                "z": data_raw.get("z", []),
                "colorscale": data_raw.get("colorscale", "YlOrRd"),
                "colorbar": {"title": data_raw.get("colorbar_title", "")},
                "hoverongaps": False,
            }],
            "layout": heat_layout,
        }

    if plot_type == "qqplot":
        theoretical = data_raw.get("theoretical", [])
        sample = data_raw.get("sample", [])
        mn = min(theoretical) if theoretical else -3
        mx = max(theoretical) if theoretical else 3
        return {
            "data": [
                {
                    "type": "scatter", "mode": "markers", "name": "Observed",
                    "x": theoretical, "y": sample,
                    "marker": {"color": PLOTLY_PALETTE[0]},
                },
                {
                    "type": "scatter", "mode": "lines", "name": "Normal",
                    "x": [mn, mx], "y": [mn, mx],
                    "line": {"color": "#ef4444", "dash": "dash"},
                },
            ],
            "layout": layout,
        }

    # Fallback — return empty chart
    return {"data": [], "layout": layout}
