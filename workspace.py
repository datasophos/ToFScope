"""Stateful explorer behind a single interactive Marimo workspace."""
import io
import csv
import json
from pathlib import Path
import traceback
from html import escape

import anywidget
import numpy as np
import traitlets
from plotly.offline import get_plotlyjs

from explorer import inspect_file, stored_peak, custom_peak, se_image, roi_from_bounds, sum_depth_window, se_mean
from plots import image_plot, profile_plot, cross_section, spectrum_plot, volume_plot, front_projection, comparison_color


class ExplorerWorkspace(anywidget.AnyWidget):
    _esm = Path(__file__).parent / 'web/workspace.js'
    _css = Path(__file__).parent / 'web/workspace.css'
    initial = traitlets.Dict().tag(sync=True)
    plotly_js = traitlets.Unicode().tag(sync=True)

    def __init__(self, path):
        super().__init__()
        self.revision = 0
        self.logarithmic = True
        self.relative = False
        self.percentile = 70
        self.opacity = .12
        self.stretch = 1.2
        self.quality = 'Fast'
        self.load_file(path)
        self.plotly_js = get_plotlyjs()
        figures=self.figures()
        self.initial = dict(state=self.state(), figures=figures)
        self.on_msg(self.handle_message)

    def load_file(self, path):
        meta = inspect_file(path)
        index = min(meta['peaks'], key=lambda p: abs(p['mass']-27))['index']
        volume = stored_peak(meta['path'], index)
        self.meta = meta
        self.index = index
        self.volume = volume
        self.frames = (0, len(volume)-1)
        self.depth_window = None
        self.frame = 0
        self.roi = (0, volume.shape[2]-1, 0, volume.shape[1]-1)
        self.comparisons = []
        self.comparison_volumes = {}
        self.next_comparison_id = 0
        self.map_projection = True
        self.custom = False
        p = meta['peaks'][index]
        self.low, self.high = p['low'], p['high']
        self.draft = (self.low, self.high)
        self.draft_frames = self.frames
        self.set_color_range()

    def set_color_range(self):
        sample = self.volume[::max(1,len(self.volume)//64)]
        positive = sample[sample > 0]
        self.color_max = float(np.percentile(positive,99.5)) if len(positive) else 1.

    @property
    def label(self):
        return (f'Custom {self.low:.4f}–{self.high:.4f} Th' if self.custom else
                f"{self.meta['peaks'][self.index]['mass']:.4f} Th · {self.meta['peaks'][self.index]['label']}")

    def state(self):
        return dict(name=self.meta['name'], path=self.meta['path'], shape=list(self.meta['shape']),
                    gib=round(self.meta['bytes']/2**30,2), peaks=self.meta['peaks'],
                    fov=self.meta['fov_um'], raw=self.meta['raw_shape'] is not None,
                    raw_shape=self.meta['raw_shape'], index=self.index, comparisons=self.comparisons, map_projection=self.map_projection,
                    frame=self.frame, frames=self.frames, depth_window=self.depth_window,
                    roi=self.roi, low=self.low, high=self.high,
                    draft=self.draft, draft_frames=self.draft_frames, custom=self.custom,
                    label=self.label, log=self.logarithmic, relative=self.relative,
                    percentile=self.percentile, opacity=self.opacity, stretch=self.stretch,
                    quality=self.quality, volume_details=getattr(self,'volume_details',None),
                    revision=self.revision)

    def figures(self, keys=None):
        keys = keys or ['ion','front','se','profile','xz','yz','spectrum','volume']
        result = {}
        selected_frames = self.depth_window or self.frames
        selected_volume = self.volume[selected_frames[0]-self.frames[0]:selected_frames[1]-self.frames[0]+1]
        for key in keys:
            if key == 'ion':
                if self.depth_window or self.map_projection:
                    data=sum_depth_window(self.volume,self.frames,selected_frames)
                    positive=data[data>0]
                    vmax=float(np.percentile(positive,99.5)) if len(positive) else 1.
                    title=f'Top projection · frames {selected_frames[0]}–{selected_frames[1]} (Σ{len(selected_volume)})'
                else:
                    data=self.volume[self.frame-self.frames[0]]
                    vmax=self.color_max
                    title=f'Ion map · frame {self.frame}'
                fig = image_plot(data,title,self.meta['fov_um'],self.logarithmic,vmax,self.roi,
                                  intensity_label='Sum intensity' if self.depth_window or self.map_projection else 'Intensity')
                fig.update_layout(dragmode='drawrect', newshape=dict(line_color='#d18c24',fillcolor='rgba(209,140,36,.06)'))
                # The server owns the single snapped ROI. Reset Plotly's drawn
                # shape edits on each response without resetting axis uirevision.
                fig.update_layout(editrevision=self.revision)
                full = (0,self.volume.shape[2]-1,0,self.volume.shape[1]-1)
                fig.layout.shapes[0].update(editable=self.roi != full, fillcolor='rgba(209,140,36,.03)')
            elif key == 'se':
                if self.depth_window:
                    data,count=se_mean(self.meta['path'],self.meta['image_names'],*self.depth_window)
                    title=f'SE mean · frames {selected_frames[0]}–{selected_frames[1]} ({count} images)'
                else:
                    data = se_image(self.meta['path'],self.meta['image_names'],self.frame)
                    title=f'SE image · index {self.frame}'
                fig = image_plot(data if data is not None else np.zeros((2,2)),
                                  title if data is not None else 'No SE image for this index',gray=True,
                                  intensity_label='Mean SE signal' if self.depth_window else 'Intensity')
            elif key == 'profile':
                fig, _ = profile_plot(self.volume,self.frames,self.roi,self.frame,self.label,
                                      self.comparison_curves(),self.relative)
                fig.update_layout(dragmode=False, hovermode='x unified')
                fig.layout.shapes[0].update(line=dict(color='#d18c24',width=2),
                                            visible=not self.map_projection or self.depth_window is not None)
                if self.depth_window:
                    fig.add_vrect(x0=self.depth_window[0],x1=self.depth_window[1],
                                  fillcolor='rgba(209,140,36,.18)',line_color='#d18c24',
                                  line_width=2,editable=False)
            elif key == 'front':
                fig = front_projection(selected_volume,selected_frames,self.roi,self.meta['fov_um'],self.logarithmic)
                fig.add_hline(y=self.frame,line_color='#d18c24',line_width=1,
                              visible=not self.map_projection or self.depth_window is not None)
            elif key in ('xz','yz'):
                fig = cross_section(selected_volume,selected_frames,self.roi,key.upper(),self.meta['fov_um'],self.logarithmic,self.color_max)
                fig.add_hline(y=self.frame,line_color='#d18c24',line_width=1,
                              visible=not self.map_projection or self.depth_window is not None)
            elif key == 'spectrum':
                fig = spectrum_plot(self.meta,*self.draft)
                for c in self.comparisons:
                    fig.add_vrect(x0=c['low'],x1=c['high'],fillcolor=c['color'],opacity=.12,
                                  line=dict(color=c['color'],width=1),layer='below')
                fig.update_xaxes(rangeslider_visible=False)
                # Spectrum selection is one-dimensional and handled by the
                # widget. Plotly's 2D drawrect leaves zero-height shapes for a
                # horizontal drag and lets trace/shape hit targets intercept it.
                fig.update_layout(dragmode=False)
                fig.layout.shapes[0].update(editable=False,fillcolor='rgba(209,140,36,.15)')
            elif key == 'volume':
                fig, preview_shape = volume_plot(selected_volume,selected_frames,self.roi,self.meta['fov_um'],
                                      self.percentile,self.opacity,self.stretch,self.logarithmic,self.quality)
                source='Custom integration' if self.custom else self.label
                x0,x1,y0,y1=self.roi
                fig.update_layout(title=dict(text=f'3D ion volume · {escape(source)}<br>'
                    f'<sup>Mass {self.low:.4f}–{self.high:.4f} Th · frames {selected_frames[0]}–{selected_frames[1]} '
                    f'· X {x0}–{x1}, Y {y0}–{y1} px</sup>',font=dict(size=14)),margin=dict(t=66))
                threshold=None
                if fig.data and fig.data[0].type=='volume':
                    threshold=float(np.expm1(fig.data[0].isomin) if self.logarithmic else fig.data[0].isomin)
                self.volume_details=dict(preview_shape=list(preview_shape),threshold=threshold)
            else:
                continue
            fig.update_layout(autosize=True)
            fig.layout.height = None
            fig.layout.width = None
            fig.update_layout(uirevision=f'{self.meta["path"]}:{key}')
            result[key] = json.loads(fig.to_json())
        return result

    def comparison_curves(self):
        """Align every comparison to the active frame domain; gaps remain missing."""
        x0,x1,y0,y1 = self.roi
        curves = []
        for c in self.comparisons:
            values = np.full(self.frames[1]-self.frames[0]+1,np.nan)
            first,last = max(c['frames'][0],self.frames[0]),min(c['frames'][1],self.frames[1])
            if first <= last:
                data = (stored_peak(self.meta['path'],c['index']) if c['index'] is not None
                        else self.comparison_volumes[c['id']])
                offset = c['frames'][0]
                values[first-self.frames[0]:last-self.frames[0]+1] = data[first-offset:last-offset+1,y0:y1+1,x0:x1+1].mean(axis=(1,2),dtype=np.float64)
            curves.append((c['label'],values,c['color']))
        return curves

    def add_comparison(self, payload):
        index = payload.get('index')
        if index is not None:
            index = int(index)
            if not 0 <= index < len(self.meta['peaks']):
                raise ValueError('Unknown comparison channel.')
            if any(c['index']==index for c in self.comparisons):
                return
            peak = self.meta['peaks'][index]
            low,high = peak['low'],peak['high']
            first,last = 0,self.meta['shape'][0]-1
            label = f"{peak['mass']:.4f} Th · {peak['label']}"
            volume = None
        else:
            low,high = map(float,payload['bounds'])
            first,last = map(int,payload['frames'])
            if any(c['index'] is None and (c['low'],c['high'])==(low,high) and c['frames']==[first,last] for c in self.comparisons):
                return
            def progress(done,total):
                if done%10==0 or done==total:
                    self.send(dict(progress=dict(done=done,total=total)))
            volume = custom_peak(self.meta['path'],low,high,first,last,progress)
            label = f'Custom {low:.4f}–{high:.4f} Th'
        identifier = self.next_comparison_id
        if index is None:
            label += f' · W{identifier+1} · frames {first}–{last}'
        descriptor = dict(id=identifier,index=index,label=label,low=low,high=high,
                          frames=[first,last],color=comparison_color(identifier))
        if volume is not None:
            self.comparison_volumes[identifier] = volume
        self.comparisons.append(descriptor)
        self.next_comparison_id += 1

    def handle_message(self, widget, content, buffers):
        event = content.get('event')
        p = content.get('payload',{})
        keys = []
        relayout = {}
        try:
            if event == 'frame':
                self.map_projection = False
                self.frame = int(np.clip(round(float(p['frame'])),*self.frames))
                if self.depth_window:
                    self.depth_window=None
                    self.draft_frames=self.frames
                    keys=['ion','front','se','profile','xz','yz','volume']
                else:
                    keys = ['ion','se']
                    relayout = {'profile':{'shapes[0].x0':self.frame,'shapes[0].x1':self.frame,'shapes[0].visible':True}}
                    relayout.update({k:{'shapes[0].y0':self.frame,'shapes[0].y1':self.frame,'shapes[0].visible':True} for k in ['xz','yz']})
                    relayout['front']={'shapes[1].y0':self.frame,'shapes[1].y1':self.frame,'shapes[1].visible':True}
            elif event == 'depth_window':
                bounds = np.asarray(p['bounds'],dtype=float)
                if bounds.shape != (2,) or not np.isfinite(bounds).all():
                    raise ValueError('Depth window must contain two finite frame limits.')
                first,last = sorted(int(np.clip(round(v),*self.frames)) for v in bounds)
                self.map_projection = True
                self.depth_window = (first,last)
                self.draft_frames = (first,last)
                self.frame = last
                keys = ['ion','front','se','profile','xz','yz','volume']
            elif event == 'clear_depth_window':
                self.map_projection = True
                self.depth_window = None
                self.draft_frames = self.frames
                keys = ['ion','front','se','profile','xz','yz','volume']
            elif event == 'peak':
                index = int(p['index'])
                if not 0 <= index < len(self.meta['peaks']):
                    raise ValueError('Unknown mass channel.')
                volume = stored_peak(self.meta['path'],index)
                self.index,self.volume = index,volume
                self.frames = (0,len(volume)-1)
                self.frame = int(np.clip(self.frame,*self.frames))
                self.custom = False
                peak = self.meta['peaks'][index]
                self.low,self.high = peak['low'],peak['high']
                self.draft = (self.low,self.high)
                self.draft_frames = self.depth_window or self.frames
                self.set_color_range()
                keys = None
            elif event == 'roi':
                self.roi = roi_from_bounds(p['bounds'],self.meta['shape'],self.meta['fov_um'])
                keys = ['ion','front','profile','xz','yz','volume']
            elif event == 'roi_pixels':
                roi = tuple(int(v) for v in p['roi'])
                if not (len(roi)==4 and 0<=roi[0]<=roi[1]<self.volume.shape[2] and 0<=roi[2]<=roi[3]<self.volume.shape[1]):
                    raise ValueError('ROI must contain valid inclusive pixel limits.')
                self.roi = roi
                keys = ['ion','front','profile','xz','yz','volume']
            elif event == 'reset_roi':
                self.roi = (0,self.volume.shape[2]-1,0,self.volume.shape[1]-1)
                keys = ['ion','front','profile','xz','yz','volume']
            elif event == 'window':
                low,high = sorted(float(v) for v in p['bounds'])
                if not np.isfinite([low,high]).all():
                    raise ValueError('Mass bounds must be finite.')
                low = max(float(self.meta['masses'].min()),low)
                high = min(float(self.meta['masses'].max()),high)
                if low >= high:
                    raise ValueError('Lower mass limit must be smaller than upper limit.')
                self.draft = (low,high)
                keys = ['spectrum']
            elif event == 'draft_frames':
                first,last = map(int,p['frames'])
                if not 0 <= first <= last < self.meta['shape'][0]:
                    raise ValueError('Integration frame limits must lie within the acquisition.')
                self.draft_frames = (first,last)
            elif event == 'integrate':
                low,high = map(float,p['bounds'])
                first,last = map(int,p['frames'])
                def progress(done,total):
                    if done % 10 == 0 or done == total:
                        self.send(dict(progress=dict(done=done,total=total)))
                volume = custom_peak(self.meta['path'],low,high,first,last,progress)
                self.volume,self.frames = volume,(first,last)
                if self.depth_window:
                    lo,hi = max(first,self.depth_window[0]),min(last,self.depth_window[1])
                    self.depth_window = (lo,hi) if lo<=hi else None
                self.frame = int(np.clip(self.frame,first,last))
                self.low,self.high = low,high
                self.draft,self.draft_frames = (low,high),(first,last)
                self.custom = True
                self.set_color_range()
                keys = None
            elif event == 'comparison_add':
                self.add_comparison(p)
                keys = ['profile','spectrum']
            elif event == 'comparison_remove':
                identifier = int(p['id'])
                self.comparisons = [c for c in self.comparisons if c['id']!=identifier]
                self.comparison_volumes.pop(identifier,None)
                keys = ['profile','spectrum']
            elif event == 'comparison_clear':
                self.comparisons.clear()
                self.comparison_volumes.clear()
                keys = ['profile','spectrum']
            elif event == 'display':
                self.logarithmic = bool(p.get('log',self.logarithmic))
                self.relative = bool(p.get('relative',self.relative))
                self.percentile = float(np.clip(float(p.get('percentile',self.percentile)),0,99))
                self.opacity = float(np.clip(float(p.get('opacity',self.opacity)),.02,.4))
                self.stretch = float(np.clip(float(p.get('stretch',self.stretch)),.2,3))
                self.quality = p.get('quality',self.quality)
                keys = ['ion','front','profile','xz','yz','volume']
            elif event == 'open':
                self.load_file(p['path'])
                keys = None
            elif event == 'export':
                self.export(p['format'])
                return
            else:
                raise ValueError('Unknown workspace action.')
            self.revision += 1
            figures = self.figures(keys) if keys is None or keys else {}
            self.send(dict(state=self.state(),figures=figures,relayout=relayout))
        except (ValueError,KeyError,OSError,TypeError) as exc:
            self.send(dict(error=str(exc),state=self.state()))
        except Exception as exc:
            traceback.print_exc()
            self.send(dict(error=f'Unexpected error: {exc}',state=self.state()))

    def export(self, format):
        selected_frames = self.depth_window or self.frames
        if format == 'csv':
            x0,x1,y0,y1 = self.roi
            selected = self.volume[selected_frames[0]-self.frames[0]:selected_frames[1]-self.frames[0]+1]
            profile = selected[:,y0:y1+1,x0:x1+1].mean(axis=(1,2),dtype=np.float64)
            out = io.StringIO()
            writer = csv.writer(out)
            curves = self.comparison_curves()
            writer.writerow(['frame','roi_mean_intensity',*[f"{c['label']} [comparison {c['id']+1}]" for c in self.comparisons]])
            for i,z in enumerate(range(selected_frames[0],selected_frames[1]+1)):
                offset = z-self.frames[0]
                writer.writerow([z,f'{profile[i]:.9g}',*[f'{c[1][offset]:.9g}' if np.isfinite(c[1][offset]) else '' for c in curves]])
            filename,text = 'depth-profile.csv',out.getvalue()
        else:
            recipe = dict(dataset=self.meta['path'],signal=self.label,source='raw_reconstruction' if self.custom else 'stored',
                          lower_Th=self.low,upper_Th=self.high,frames_inclusive=selected_frames,
                          loaded_frames_inclusive=self.frames,
                          roi_pixels_inclusive=self.roi,z_units='frame',fov_um=self.meta['fov_um'],comparisons=self.comparisons,schema_version=2)
            filename,text = 'mass-window.json',json.dumps(recipe,indent=2)
        self.send(dict(download=dict(filename=filename,text=text),state=self.state()))
