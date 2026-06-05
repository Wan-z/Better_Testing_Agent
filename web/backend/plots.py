"""Convert HTA PlotSpec objects to Plotly JSON dicts."""

from __future__ import annotations

from typing import Any


PLOTLY_PALETTE = ["#4f46e5", "#94a3b8", "#10b981", "#f59e0b", "#ef4444"]
# Edge colour per dependence form for the dependence-network graph (Xiang et al. Fig 6/8):
# "different colours for different binary interactions".
FORM_COLORS = {
    "MONOTONE": "#6366f1", "LINEAR": "#0ea5e9", "PARABOLIC": "#f59e0b",
    "SINUSOIDAL": "#ec4899", "CHECKERBOARD": "#10b981", "COMPLEX": "#ef4444",
}
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

    if plot_type == "bet_interaction":
        # Xiang-style binary-interaction EDA scatter on the empirical-copula unit square.
        # A faint checkerboard heatmap shows the dominant interaction's ± regions on the
        # 2^d grid; points are coloured by which region (sign) they fall in — or by a
        # known subgroup label when one is supplied — so heterogeneity becomes visible.
        u = data_raw.get("u", [])
        v = data_raw.get("v", [])
        g = int(data_raw.get("grid_size", 4)) or 4
        region_z = data_raw.get("region_z", [])
        color_by = data_raw.get("color_by", "interaction")
        centers = [(k + 0.5) / g for k in range(g)]

        traces = []
        if region_z:
            traces.append({
                "type": "heatmap",
                "x": centers, "y": centers, "z": region_z,
                "colorscale": [[0.0, "#bfdbfe"], [1.0, "#fde68a"]],  # − blue / + amber
                "zmin": -1, "zmax": 1, "xgap": 1, "ygap": 1,
                "showscale": False, "opacity": 0.45, "hoverinfo": "skip",
            })

        if color_by == "label":
            labels = [str(lab) for lab in data_raw.get("labels", [])]
            cats: list[str] = []
            for lab in labels:
                if lab not in cats:
                    cats.append(lab)
            for i, cat in enumerate(cats):
                xs_pts = [uu for uu, lab in zip(u, labels) if lab == cat]
                ys_pts = [vv for vv, lab in zip(v, labels) if lab == cat]
                traces.append({
                    "type": "scatter", "mode": "markers", "name": cat,
                    "x": xs_pts, "y": ys_pts,
                    "marker": {"color": PLOTLY_PALETTE[i % len(PLOTLY_PALETTE)],
                               "size": 7, "opacity": 0.85,
                               "line": {"width": 0.5, "color": "#ffffff"}},
                })
        else:
            point_sign = data_raw.get("point_sign", [])
            for name, sgn, color in (("Interaction +", 1, "#b45309"),
                                     ("Interaction −", -1, "#1d4ed8")):
                xs_pts = [uu for uu, s in zip(u, point_sign) if s == sgn]
                ys_pts = [vv for vv, s in zip(v, point_sign) if s == sgn]
                traces.append({
                    "type": "scatter", "mode": "markers", "name": name,
                    "x": xs_pts, "y": ys_pts,
                    "marker": {"color": color, "size": 7, "opacity": 0.85,
                               "line": {"width": 0.5, "color": "#ffffff"}},
                })

        axis = {"range": [0, 1], "tick0": 0, "dtick": 1.0 / g, "showgrid": True,
                "gridcolor": "#cbd5e1", "zeroline": False, "constrain": "domain"}
        bet_layout = {
            **layout,
            "xaxis": {**layout.get("xaxis", {}), **axis},
            "yaxis": {**layout.get("yaxis", {}), **axis, "scaleanchor": "x"},
            "legend": {"orientation": "h", "y": -0.2, "x": 0},
        }
        return {"data": traces, "layout": bet_layout}

    if plot_type == "bet_network":
        # Network of nonlinear relationships (Xiang et al. 2023, Fig. 6/8): variables are
        # nodes, each edge is a significant BET dependence, edges coloured by binary
        # interaction (form). One line trace per form gives the coloured legend.
        nodes = data_raw.get("nodes", [])
        edges = data_raw.get("edges", [])
        by_name = {nd["name"]: nd for nd in nodes}
        forms_order: list[str] = []
        for e in edges:
            f = e.get("form", "COMPLEX")
            if f not in forms_order:
                forms_order.append(f)
        traces = []
        for f in forms_order:
            ex: list[Any] = []
            ey: list[Any] = []
            for e in edges:
                if e.get("form") != f:
                    continue
                a, b = by_name.get(e["x"]), by_name.get(e["y"])
                if not a or not b:
                    continue
                ex += [a["x"], b["x"], None]
                ey += [a["y"], b["y"], None]
            traces.append({
                "type": "scatter", "mode": "lines", "name": f.title(),
                "x": ex, "y": ey, "opacity": 0.9, "hoverinfo": "skip",
                "line": {"color": FORM_COLORS.get(f, "#64748b"), "width": 3.5},
            })
        degs = [int(nd.get("degree", 1)) for nd in nodes]
        max_deg = max(degs) if degs else 1
        show_all = len(nodes) <= 25
        thresh = max(2, max_deg * 0.5)
        traces.append({
            "type": "scatter", "mode": "markers+text", "name": "variables",
            "x": [nd["x"] for nd in nodes], "y": [nd["y"] for nd in nodes],
            "text": [nd["name"] if (show_all or nd.get("degree", 1) >= thresh) else ""
                     for nd in nodes],
            "textposition": "top center",
            "textfont": {"size": 11, "color": "#334155"},
            "hovertext": [f"{nd['name']} — {nd.get('degree', 1)} link(s)" for nd in nodes],
            "hoverinfo": "text", "showlegend": False,
            "marker": {
                "size": [9 + 11 * (int(nd.get("degree", 1)) / max_deg) for nd in nodes],
                "color": "#1e293b", "line": {"width": 1.5, "color": "#ffffff"},
            },
        })
        net_layout = {
            **layout,
            "xaxis": {"visible": False, "range": [0, 1]},
            "yaxis": {"visible": False, "range": [0, 1], "scaleanchor": "x"},
            "showlegend": True,
            "legend": {"orientation": "h", "y": -0.04, "x": 0},
            "margin": {"t": 30, "r": 10, "b": 10, "l": 10},
        }
        return {"data": traces, "layout": net_layout}

    # Fallback — return empty chart
    return {"data": [], "layout": layout}
