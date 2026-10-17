"""Plotly views. Display transformations never alter the analysis arrays."""
import numpy as np
import plotly.graph_objects as go
from html import escape
from explorer import preview_grid

TEAL = '#078d83'
GOLD = '#d18c24'


def comparison_color(index):
    palette = ['#d18c24','#6a5acd','#d14d72','#2279b5','#8c613c','#609b35','#b85ac0','#507d89']
    return palette[index] if index < len(palette) else f'hsl({(index*137.508)%360:.1f},60%,43%)'


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


def spectrum_plot(meta, low=None, high=None, *, intervals=None, window_ids=None, selected_id=None):
    fig = go.Figure(go.Scattergl(x=meta['masses'], y=meta['spectrum'], mode='lines',
                               line=dict(color=TEAL, width=1), name='Sum spectrum'))
    windows=list(intervals if intervals is not None else [(low,high)])
    identifiers=list(window_ids if window_ids is not None else range(len(windows)))
    rows=list(zip(identifiers,windows))
    rows.sort(key=lambda row:row[0]!=selected_id)
    for identifier,(lower,upper) in rows:
        fig.add_vrect(x0=lower,x1=upper,fillcolor=GOLD,opacity=.22,
                      line=dict(color=GOLD,width=2 if identifier==selected_id else 1),
                      name=f'draft:{identifier}',editable=False)
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


def profile_plot(volume, frames, roi, selected_frame, label, comparison=None, relative=False,calibration=None,unit="nm"):
    from depth_calibration import convert_depth
    x0, x1, y0, y1 = roi
    profile = volume[:, y0:y1+1, x0:x1+1].mean(axis=(1, 2), dtype=np.float64)
    z = np.arange(frames[0], frames[1] + 1)
    coords=convert_depth(calibration.frame_to_depth(z),"nm",unit) if calibration else z
    curves = [(label, profile, TEAL), *(comparison or [])]
    fig = go.Figure()
    for name, values, color in curves:
        finite = values[np.isfinite(values)]
        maximum = finite.max() if finite.size else 0
        values = values / maximum if relative and maximum > 0 else values
        fig.add_trace(go.Scatter(x=coords, y=values, name=name,customdata=z,
                                mode='lines+markers' if np.count_nonzero(np.isfinite(coords)&np.isfinite(values))==1 else 'lines',
                                marker=dict(color=color,size=6),connectgaps=False,
                                line=dict(color=color, width=1.6)))
    marker=float(convert_depth(calibration.frame_to_depth(selected_frame),'nm',unit)) if calibration else selected_frame
    fig.add_vline(x=marker if np.isfinite(marker) else 0,visible=bool(np.isfinite(marker)),line_color='#8b99a8',line_dash='dot')
    fig.update_xaxes(title=f'Depth ({unit})' if calibration else 'Depth frame')
    fig.update_yaxes(title='Relative to each curve’s maximum' if relative else 'Mean intensity / pixel')
    layout(fig, 'Depth profile · selected spatial ROI', 290)
    fig.update_layout(meta=dict(axis_kind='depth' if calibration else 'frame',unit=unit if calibration else 'frame',
                               calibrated_span=[calibration.anchors[0].frame,calibration.anchors[-1].frame] if calibration else None))
    if calibration:fig.update_layout(title=f'Depth profile · calibrated frames 0–{calibration.anchors[-1].frame}')
    fig.update_layout(margin=dict(t=86), title=dict(y=.98,yanchor='top'),
                      legend=dict(orientation='h',y=1.02,yanchor='bottom',maxheight=50,font=dict(size=10)))
    return fig, profile


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


def front_projection(volume, frames, roi, fov, log):
    """XZ projection sums the ROI's Y rows, retaining X and each depth layer."""
    x0,x1,y0,y1 = roi
    data = volume[:,y0:y1+1,:].sum(axis=1,dtype=np.float64)
    nx = volume.shape[2]
    x = (np.arange(nx)+.5)*fov/nx if fov else np.arange(nx)
    shown = np.log1p(np.maximum(data,0)) if log else data
    fig = go.Figure(go.Heatmap(z=shown,x=x,y=np.arange(frames[0],frames[1]+1),
        customdata=data,colorscale='Viridis',zmin=0,
        colorbar=dict(title='logₑ(1+ΣI)' if log else 'Sum intensity',thickness=10),
        hovertemplate='X=%{x:.3f}<br>Frame=%{y}<br>Y-sum=%{customdata:.5g}<extra></extra>'))
    fig.update_xaxes(title=f'X ({"µm" if fov else "pixel"})')
    fig.update_yaxes(title='Depth frame',autorange='reversed')
    sx=fov/nx if fov else 1
    fig.add_vrect(x0=(x0 if fov else x0-.5)*sx,x1=(x1+1 if fov else x1+.5)*sx,
                  line=dict(color=GOLD,width=1),fillcolor='rgba(209,140,36,.04)')
    return layout(fig,f'Front projection · sum Y {y0}–{y1} px',330)


def _layer_volume_plot(previews,layer_styles,*,tiled=False,scale_mode='independent',stretch=1.2,log=True,shared_range=None):
    """Plot aligned previews; colors transform display values only."""
    from plotly.subplots import make_subplots
    from signals import interval_label
    if scale_mode not in ('independent','shared'):raise ValueError('Unknown volume intensity scale mode.')
    if tiled and len(previews)>4:raise ValueError('Tile pages contain at most four scenes.')
    styles={s.id:s for s in layer_styles}
    count=len(previews);cols=2 if count>1 else 1;rows=max(1,int(np.ceil(count/cols)))
    titles=[escape(p.recipe.label) for p in previews] if tiled else None
    fig=make_subplots(rows=rows,cols=cols,specs=[[{'type':'scene'}]*cols for _ in range(rows)],subplot_titles=titles) if tiled else go.Figure()
    transform=lambda a:np.log1p(np.maximum(a,0)) if log else a
    positive=[p.values[np.isfinite(p.values)&(p.values>0)] for p in previews]
    nonempty=[v for v in positive if v.size]
    all_values=np.concatenate(nonempty) if nonempty else np.array([])
    common_hi=float(np.percentile(transform(all_values),99.7)) if all_values.size else 1.
    common_lo=0.
    if shared_range is not None:common_lo,common_hi=shared_range
    layer_meta=[]
    for i,(preview,nonzero) in enumerate(zip(previews,positive)):
        style=styles[preview.layer_id];scene='scene' if i==0 or not tiled else f'scene{i+1}'
        grid=preview.grid;zz,yy,xx=np.meshgrid(grid.z,grid.y,grid.x,indexing='ij');values=transform(preview.values)
        label=preview.recipe.label
        lower=None;cmin=0.;cmax=1.
        if nonzero.size:
            lower=float(np.percentile(transform(nonzero),style.percentile));upper=float(np.percentile(transform(nonzero),99.7))
            upper=max(upper,lower+max(abs(lower)*.01,1e-6))
            cmin,cmax=(common_lo,common_hi) if scale_mode=='shared' else (0.,upper)
            finite=np.isfinite(values)
            covered_indices=np.where(finite)
            thin=any(np.unique(axis).size<2 for axis in covered_indices)
            if thin or np.ptp(values[finite])==0:
                shown=finite&(values>=lower)
                trace=go.Scatter3d(x=xx[shown],y=yy[shown],z=zz[shown],name=label,scene=scene,mode='markers',
                    marker=dict(size=3,color=values[shown],cmin=cmin,cmax=cmax,colorscale=style.colorscale,opacity=style.opacity),hoverinfo='skip')
            else:
                trace=go.Volume(x=xx.ravel(),y=yy.ravel(),z=zz.ravel(),value=values.ravel(),name=label,scene=scene,
                    isomin=lower,isomax=upper,cmin=cmin,cmax=cmax,opacity=style.opacity,surface_count=10,
                    colorscale=style.colorscale,showscale=False,showlegend=True,caps=dict(x_show=False,y_show=False,z_show=False),hoverinfo='skip')
            fig.add_trace(trace)
        else:
            fig.add_annotation(text=f'{label}: no positive signal in this selection',xref='paper',yref='paper',x=.5,y=.5-i*.05,showarrow=False)
        extent_x,extent_y=grid.xy_extent or (1.,1.);extent=max(extent_x,extent_y)
        fig.update_layout(**{scene:dict(xaxis_title='X (µm)' if grid.physical_xy else 'X (pixel)',
            yaxis_title='Y (µm)' if grid.physical_xy else 'Y (pixel)',zaxis=dict(title='Depth frame',autorange='reversed'),
            aspectmode='manual',aspectratio=dict(x=extent_x/extent,y=extent_y/extent,z=stretch),uirevision=f'layer:{preview.layer_id}' if tiled else 'overlay-camera')})
        layer_meta.append(dict(id=preview.layer_id,label=preview.recipe.label,intervals=preview.recipe.intervals,
            frames=preview.recipe.frames,shape=preview.values.shape,valid_voxels=int(np.count_nonzero(preview.coverage)),
            threshold=float(np.expm1(lower) if log else lower) if lower is not None else None,
            intensity_scale=scale_mode,scale_min=cmin,scale_max=cmax,colorscale=style.colorscale))
    if not previews:fig.add_annotation(text='No visible layers · enable a layer in Layers',showarrow=False)
    fig.update_layout(meta=dict(layers=layer_meta,scale_mode=scale_mode),legend=dict(orientation='h',font=dict(size=10)))
    title='3D ion layers · tiled' if tiled else '3D ion layers · overlay'
    if len(previews)==1:title+=' · '+escape(previews[0].recipe.label)+'<br><sup>Mass '+interval_label(previews[0].recipe.intervals)+'</sup>'
    return layout(fig,title,550,dark=True)


def overlay_volume_plot(previews,layer_styles,*,scale_mode='independent',stretch=1.2,log=True,shared_range=None):
    return _layer_volume_plot(previews,layer_styles,scale_mode=scale_mode,stretch=stretch,log=log,shared_range=shared_range)


def tiled_volume_plot(previews,layer_styles,*,scale_mode='independent',stretch=1.2,log=True,shared_range=None):
    return _layer_volume_plot(previews,layer_styles,tiled=True,scale_mode=scale_mode,stretch=stretch,log=log,shared_range=shared_range)
