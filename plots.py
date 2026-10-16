"""Plotly views. Display transformations never alter the analysis arrays."""
import numpy as np
import plotly.graph_objects as go
from explorer import preview_grid

TEAL = '#078d83'
GOLD = '#d18c24'


def layout(fig, title, height=330, dark=False):
    fig.update_layout(
        title=dict(text=title, font=dict(size=15)), height=height,
        template='plotly_dark' if dark else 'plotly_white',
        paper_bgcolor='#101f2e' if dark else '#ffffff',
        plot_bgcolor='#101f2e' if dark else '#ffffff',
        font=dict(family='Inter, system-ui, sans-serif', size=11),
        margin=dict(l=55, r=20, t=48, b=45),
        uirevision=title,
    )
    fig.update_xaxes(gridcolor='#e9edf0')
    fig.update_yaxes(gridcolor='#e9edf0')
    if dark:
        fig.update_layout(modebar=dict(bgcolor='rgba(16,31,46,.94)',
                                       color='#c8d8e5',activecolor='#6bdbc1'))
    return fig


def spectrum_plot(meta, low, high):
    fig = go.Figure(go.Scattergl(x=meta['masses'], y=meta['spectrum'], mode='lines',
                               line=dict(color=TEAL, width=1), name='Sum spectrum'))
    fig.add_vrect(x0=low, x1=high, fillcolor=GOLD, opacity=.22, line_width=1)
    fig.update_xaxes(title='Mass / charge (Th)', rangeslider_visible=True,
                     rangeslider_thickness=.12)
    fig.update_yaxes(title='Summed intensity', type='log')
    return layout(fig, 'Mass spectrum · highlighted integration window', 280)


def image_plot(data, title, fov=None, log=False, vmax=None, roi=None, gray=False, intensity_label='Intensity'):
    ny, nx = data.shape
    x = (np.arange(nx) + .5) * fov / nx if fov else np.arange(nx)
    y = (np.arange(ny) + .5) * fov / ny if fov else np.arange(ny)
    transformed = np.log1p(np.maximum(data, 0)) if log else data
    high = float(np.log1p(vmax)) if log and vmax is not None else vmax
    if gray:
        low, high = np.percentile(data, [2, 98])
    else:
        low = 0
    fig = go.Figure(go.Heatmap(
        z=transformed, x=x, y=y, customdata=data, zmin=low, zmax=high,
        colorscale='Gray' if gray else 'Viridis',
        colorbar=dict(title='logₑ(1+ΣI)' if log and intensity_label=='Sum intensity' else 'logₑ(1+I)' if log else intensity_label, thickness=10),
        hovertemplate='x=%{x:.3f}<br>y=%{y:.3f}<br>'+intensity_label+'=%{customdata:.5g}<extra></extra>'))
    unit = 'µm' if fov else 'pixel'
    fig.update_xaxes(title=f'X ({unit})', constrain='domain')
    fig.update_yaxes(title=f'Y ({unit})', autorange='reversed', scaleanchor='x')
    if roi:
        x0, x1, y0, y1 = roi
        sx, sy = (fov / nx, fov / ny) if fov else (1, 1)
        fig.add_shape(type='rect', x0=(x0-.5 if not fov else x0)*sx,
                      x1=(x1+.5 if not fov else x1+1)*sx,
                      y0=(y0-.5 if not fov else y0)*sy,
                      y1=(y1+.5 if not fov else y1+1)*sy,
                      line=dict(color=GOLD, width=2))
    return layout(fig, title, 390)


def profile_plot(volume, frames, roi, selected_frame, label, comparison=None, relative=False):
    x0, x1, y0, y1 = roi
    profile = volume[:, y0:y1+1, x0:x1+1].mean(axis=(1, 2), dtype=np.float64)
    z = np.arange(frames[0], frames[1] + 1)
    curves = [(label, profile, TEAL)]
    if comparison is not None:
        name, other = comparison
        curves.append((name, other[frames[0]:frames[1]+1, y0:y1+1, x0:x1+1].mean(axis=(1, 2), dtype=np.float64), GOLD))
    fig = go.Figure()
    for name, values, color in curves:
        values = values / values.max() if relative and values.max() > 0 else values
        fig.add_trace(go.Scatter(x=z, y=values, name=name, mode='lines', line=dict(color=color, width=1.6)))
    fig.add_vline(x=selected_frame, line_color='#8b99a8', line_dash='dot')
    fig.update_xaxes(title='Depth frame')
    fig.update_yaxes(title='Relative to each curve’s maximum' if relative else 'Mean intensity / pixel')
    fig.update_layout(legend=dict(orientation='h', y=1.16))
    return layout(fig, 'Depth profile · selected spatial ROI', 290), profile


def cross_section(volume, frames, roi, direction, fov, log, vmax):
    x0, x1, y0, y1 = roi
    if direction == 'XZ':
        midpoint = (y0 + y1) // 2
        data = volume[:, midpoint, x0:x1+1]
        pos = np.arange(x0, x1+1)
        denominator = volume.shape[2]
        axis = 'X'
    else:
        midpoint = (x0 + x1) // 2
        data = volume[:, y0:y1+1, midpoint]
        pos = np.arange(y0, y1+1)
        denominator = volume.shape[1]
        axis = 'Y'
    pos = (pos + .5) * fov / denominator if fov else pos
    fig = go.Figure(go.Heatmap(
        x=pos, y=np.arange(frames[0], frames[1]+1),
        z=np.log1p(np.maximum(data, 0)) if log else data,
        zmin=0, zmax=float(np.log1p(vmax)) if log else vmax,
        colorscale='Viridis', showscale=False))
    fig.update_xaxes(title=f'{axis} (µm)' if fov else f'{axis} (pixel)')
    fig.update_yaxes(title='Depth frame', autorange='reversed')
    return layout(fig, f'{direction} section · {"Y" if direction == "XZ" else "X"} pixel {midpoint}', 310)


def volume_plot(volume, frames, roi, fov, percentile=70, opacity=.12, stretch=1.2, log=True, quality='Fast'):
    limits = (96, 32) if quality == 'Fast' else (160, 48)
    grid, axes = preview_grid(volume, frames, roi, *limits)
    z, y, x = axes
    if fov:
        y = (y + .5) * fov / volume.shape[1]
        x = (x + .5) * fov / volume.shape[2]
    zz, yy, xx = np.meshgrid(z, y, x, indexing='ij')
    positive = grid[grid > 0]
    fig = go.Figure()
    if len(positive):
        lo = float(np.percentile(positive, percentile))
        hi = float(np.percentile(positive, 99.7))
        if hi <= lo:
            hi = float(positive.max())
        if hi <= lo:
            hi = lo + max(abs(lo) * .01, 1e-6)
        values = np.log1p(grid) if log else grid
        if min(grid.shape) < 2:
            fig.add_trace(go.Scatter3d(
                x=xx.ravel(), y=yy.ravel(), z=zz.ravel(), mode='markers',
                marker=dict(size=3, color=values.ravel(), colorscale='Viridis', opacity=.65),
                hoverinfo='skip', name='Thin selection'))
        else:
            fig.add_trace(go.Volume(
            x=xx.ravel(), y=yy.ravel(), z=zz.ravel(), value=values.ravel(),
            isomin=float(np.log1p(lo)) if log else lo,
            isomax=float(np.log1p(hi)) if log else hi,
            opacity=opacity, surface_count=12, colorscale='Viridis',
            caps=dict(x_show=False, y_show=False, z_show=False),
            colorbar=dict(title='logₑ(1+I)' if log else 'Intensity', thickness=10, len=.65),
            hoverinfo='skip'))
    else:
        fig.add_annotation(text='No nonzero signal in this selection', showarrow=False)
    extent_x = (roi[1] - roi[0] + 1) / (volume.shape[2] if fov else 1)
    extent_y = (roi[3] - roi[2] + 1) / (volume.shape[1] if fov else 1)
    extent = max(extent_x, extent_y)
    fig.update_layout(scene=dict(
        xaxis_title='X (µm)' if fov else 'X (pixel)',
        yaxis_title='Y (µm)' if fov else 'Y (pixel)',
        zaxis=dict(title='Depth frame', autorange='reversed'),
        aspectmode='manual', aspectratio=dict(x=extent_x/extent, y=extent_y/extent, z=stretch),
        camera=dict(eye=dict(x=1.5, y=1.5, z=.9))),
        scene_uirevision='volume-camera')
    return layout(fig, '3D ion volume · drag to rotate', 550, dark=True), grid.shape
