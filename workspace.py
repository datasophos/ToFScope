"""Stateful explorer behind a single interactive Marimo workspace."""
import io
import csv
import json
from pathlib import Path
import traceback
from time import perf_counter
from dataclasses import asdict,replace
from html import escape

from signals import SignalRecipe,read_signal,interval_label
from integration import canonical_intervals
from server_config import ServerSettings, resolve_data_path
from file_browser import list_data_files
from depth_calibration import DepthAnchor, DepthCalibration, validate_anchors, convert_depth,calibrated_window
from isotopes import load_catalog, find_candidates, IonCandidate, ion_mz
from abundance import measure_isotopes
from volume_layers import VolumeLayer,build_layer_previews,COLORSCALES
from dataset_io import dataset_lock,file_identity,save_to_acquisition,required_space
from integration_store import IntegrationRecord,list_saved_integrations,saved_integration_info
from vendor_export import validate_native_recipe,validate_native_layout
from uuid import uuid4
import h5py

import anywidget
import numpy as np
import traitlets
from plotly.offline import get_plotlyjs

from explorer import inspect_file, stored_peak, se_image, roi_from_bounds, sum_depth_window, se_mean
from plots import image_plot, profile_plot, cross_section, spectrum_plot, volume_plot, front_projection, comparison_color,overlay_volume_plot,tiled_volume_plot


class ExplorerWorkspace(anywidget.AnyWidget):
    _esm = Path(__file__).parent / 'web/workspace.js'
    _css = Path(__file__).parent / 'web/workspace.css'
    initial = traitlets.Dict().tag(sync=True)
    plotly_js = traitlets.Unicode().tag(sync=True)
    interval_editor_js = traitlets.Unicode().tag(sync=True)
    file_browser_js = traitlets.Unicode().tag(sync=True)
    depth_editor_js = traitlets.Unicode().tag(sync=True)
    peak_helper_js = traitlets.Unicode().tag(sync=True)
    volume_layers_js = traitlets.Unicode().tag(sync=True)
    save_integration_js = traitlets.Unicode().tag(sync=True)
    dialog_plot_js = traitlets.Unicode().tag(sync=True)

    def __init__(self, path=None, settings=None):
        super().__init__()
        if settings is None and path is None:
            raise ValueError('Server settings are required without an initial acquisition.')
        self.settings=settings or ServerSettings(Path(path).expanduser().resolve().parent)
        self.meta=None
        self.revision = 0
        self.logarithmic = True
        self.relative = False
        self.percentile = 70
        self.opacity = .12
        self.stretch = 1.2
        self.quality = 'Fast'
        self.interval_editor_js=(Path(__file__).parent/'web/interval_editor.js').read_text()
        self.file_browser_js=(Path(__file__).parent/'web/file_browser.js').read_text()
        self.depth_editor_js=(Path(__file__).parent/'web/depth_editor.js').read_text()
        self.peak_helper_js=(Path(__file__).parent/'web/peak_helper.js').read_text()
        self.volume_layers_js=(Path(__file__).parent/'web/volume_layers.js').read_text()
        self.save_integration_js=(Path(__file__).parent/'web/save_integration.js').read_text()
        self.dialog_plot_js=(Path(__file__).parent/'web/dialog_plot.js').read_text()
        self.startup_error=None
        if path is not None:
            try:self.load_file(path)
            except (OSError,ValueError,KeyError) as exc:
                self.startup_error=self.safe_error(exc)
        self.plotly_js = get_plotlyjs()
        try:figures=self.figures()
        except (OSError,ValueError,KeyError,TypeError) as exc:
            self.meta=None;self.startup_error=self.safe_error(exc);figures={}
        self.initial = dict(state=self.state(), figures=figures)
        self.on_msg(self.handle_message)

    def load_file(self, path):
        with dataset_lock(path):self._load_file(path)

    def _load_file(self, path):
        # Constructor paths are internal; client open events resolve separately.
        path=resolve_data_path(self.settings,str(Path(path).resolve().relative_to(self.settings.data_root)),require_file=True)
        meta = inspect_file(path)
        index = min(meta['peaks'], key=lambda p: abs(p['mass']-27))['index']
        volume = stored_peak(meta['path'], index)
        p=meta['peaks'][index]
        recipe=SignalRecipe(source='stored',stored_index=index,intervals=((p['low'],p['high']),),
                            frames=(0,len(volume)-1),label=f"{p['mass']:.4f} Th · {p['label']}")
        if any(d<=0 for d in volume.shape):raise ValueError('Acquisition dimensions must be nonempty.')
        sample=volume[::max(1,len(volume)//64)];positive=sample[sample>0]
        color_max=float(np.percentile(positive,99.5)) if len(positive) else 1.
        identity=file_identity(path)
        saved=list_saved_integrations(path)
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
        self.active_recipe=recipe
        self.stored_recipes={index:recipe}
        self.assignments={}
        self.candidate_rows={}
        self.abundance_rows=[]
        self.abundance_context=None
        self.next_interval_id=0
        self.reset_draft(self.active_recipe.intervals)
        self.draft_frames = self.frames
        self.color_max=color_max
        self.depth_anchors=(DepthAnchor(0,0.),)
        self.calibration=None
        self.depth_unit='nm'
        self.profile_axis='frame'
        self.volume_layers=[VolumeLayer('active',recipe)]
        self.layer_sources={}
        self.layered_volume=False
        self.next_layer_id=1
        self.volume_mode='tiles'
        self.volume_scale='independent'
        self.volume_page=0
        self.depth_stretch=1.
        self.loaded_identity=identity
        self.saved_integrations=saved
        self.stale=False

    def select_saved(self,identifier):
        info=saved_integration_info(self.meta['path'],identifier)
        derivation=info['derivation']
        recipe=SignalRecipe(source='saved',saved_id=identifier,intervals=derivation['intervals'],
                            frames=derivation['frames'],label=derivation['label'])
        volume=read_signal(self.meta['path'],recipe)
        calibration=info.get('calibration');anchors=None;prepared_calibration=None
        if calibration:
            anchors=validate_anchors([DepthAnchor(**a) for a in calibration['anchors']],self.meta['shape'][0])
            prepared_calibration=DepthCalibration(anchors,self.meta['shape'][0]) if len(anchors)>1 else None
            convert_depth(1,'nm',calibration['unit'])
        self.active_recipe=recipe;self.volume=volume;self.frames=recipe.frames
        self.frame=recipe.frames[0];self.depth_window=None;self.map_projection=True
        self.custom=True;self.roi=(0,volume.shape[2]-1,0,volume.shape[1]-1)
        self.reset_draft(recipe.intervals);self.draft_frames=recipe.frames;self.set_color_range()
        if calibration:
            self.depth_anchors=anchors;self.calibration=prepared_calibration
            self.depth_unit=calibration['unit']

    def save_record(self,label=None):
        if self.active_recipe.source!='custom':raise ValueError('Apply a custom integration before saving it.')
        recipe=replace(self.active_recipe,label=label) if label is not None else self.active_recipe
        return IntegrationRecord(str(uuid4()),recipe.to_dict(),tuple(self.meta['shape'][1:3]),
            asdict(self.loaded_identity),dict(convention='per waveform and active recording channel',
            values='full XY scientific float32; no ROI, log transform or display sampling'),self.calibration_metadata())

    def public_identity(self):
        # JavaScript numbers cannot exactly represent POSIX nanosecond times.
        return {key:str(value) for key,value in asdict(self.loaded_identity).items()}

    def save_preview(self,recipe_id):
        if recipe_id!=self.active_recipe.id:raise ValueError('The active signal changed. Review the save again.')
        record=self.save_record('ToFScope_integration')
        reason=None
        try:
            with h5py.File(self.meta['path'],'r') as h5:
                validate_native_layout(h5);validate_native_recipe(h5,SignalRecipe.from_dict(record.derivation))
        except (ValueError,UnicodeError) as exc:reason=str(exc)
        if not self.settings.allow_writes:reason='Acquisition writes are disabled by the server.'
        elif not self.settings.allow_unverified_native:reason='Experimental native writes are disabled; commercial compatibility is unverified.'
        return dict(target=self.public_path(),recipe_id=recipe_id,intervals=record.derivation['intervals'],
            frames=record.derivation['frames'],spatial_shape=list(record.spatial_shape),commercial_status='unverified',
            expected_identity=self.public_identity(),required_bytes=required_space(self.loaded_identity,record),
            can_save=reason is None,reason=reason,label='ToFScope_'+str(self.active_recipe.intervals[0][0]).replace('.','p')+'_'+str(self.active_recipe.intervals[-1][1]).replace('.','p'))

    def public_path(self):
        return str(Path(self.meta['path']).relative_to(self.settings.data_root))

    def safe_error(self,exc):
        return '\n'.join([str(exc),*getattr(exc,'__notes__',[])]).replace(str(self.settings.data_root),'<data root>')

    def calibration_metadata(self):
        return dict(anchors=[dict(frame=a.frame,depth_nm=a.depth_nm) for a in self.depth_anchors],
                    unit=self.depth_unit,acquisition_frames=self.meta['shape'][0],
                    interpolation='piecewise_linear',extrapolation=False)

    def profile_coordinate(self,frame):
        if self.profile_axis=='depth' and self.calibration:
            return float(convert_depth(self.calibration.frame_to_depth(frame),'nm',self.depth_unit))
        return frame

    @property
    def view_calibration(self):
        return self.calibration if self.profile_axis=='depth' else None

    @property
    def display_stretch(self):
        return self.depth_stretch if self.view_calibration else self.stretch

    def set_color_range(self):
        sample = self.volume[::max(1,len(self.volume)//64)]
        positive = sample[sample > 0]
        self.color_max = float(np.percentile(positive,99.5)) if len(positive) else 1.

    @property
    def label(self):
        return self.active_recipe.label

    @property
    def low(self):
        return self.active_recipe.intervals[0][0] if len(self.active_recipe.intervals)==1 else None

    @property
    def high(self):
        return self.active_recipe.intervals[0][1] if len(self.active_recipe.intervals)==1 else None

    @property
    def draft_intervals(self):
        return tuple(tuple(row['bounds']) for row in self.draft_windows)

    @property
    def draft(self):
        row=next((r for r in self.draft_windows if r['id']==self.selected_interval_id),None)
        return tuple(row['bounds']) if row else None

    def reset_draft(self,intervals):
        self.draft_windows=[]
        for bounds in intervals:
            self.draft_windows.append(dict(id=self.next_interval_id,bounds=tuple(bounds)))
            self.next_interval_id+=1
        self.selected_interval_id=self.draft_windows[0]['id'] if self.draft_windows else None

    def draft_row(self,identifier):
        row=next((r for r in self.draft_windows if r['id']==identifier),None)
        if row is None:
            raise ValueError('Unknown draft interval.')
        return row

    def checked_bounds(self,bounds):
        axis=self.meta['masses']
        return canonical_intervals([bounds],(float(axis.min()),float(axis.max())))[0]

    def add_interval(self,bounds=None):
        bounds=self.checked_bounds(bounds if bounds is not None else self.draft or self.active_recipe.intervals[0])
        identifier=self.next_interval_id
        self.next_interval_id+=1
        self.draft_windows.append(dict(id=identifier,bounds=bounds))
        self.selected_interval_id=identifier

    def stored_recipe(self,index):
        if index in self.stored_recipes:return self.stored_recipes[index]
        p=self.meta['peaks'][index]
        recipe=SignalRecipe(source='stored',stored_index=index,intervals=((p['low'],p['high']),),
                            frames=(0,self.meta['shape'][0]-1),label=f"{p['mass']:.4f} Th · {p['label']}")
        self.stored_recipes[index]=recipe
        return recipe

    def available_recipes(self):
        return {r.id:r for r in [self.active_recipe,*(SignalRecipe.from_dict(c['recipe']) for c in self.comparisons)]}

    def candidate_record(self,identifier):
        if identifier not in self.candidate_rows:raise ValueError('Search for this candidate before assigning it.')
        return self.candidate_rows[identifier]

    def layer_reader(self,path,recipe):
        if recipe.id==self.active_recipe.id:return self.volume
        if recipe.id in self.layer_sources:return self.layer_sources[recipe.id]
        return read_signal(path,recipe)

    def layered_figure(self,frames):
        started=perf_counter()
        enabled=[l for l in self.volume_layers if l.visible]
        pages=max(1,(len(enabled)+3)//4)
        self.volume_page=min(self.volume_page,pages-1)
        all_previews=build_layer_previews(self.meta['path'],enabled,self.roi,tuple(frames),quality=self.quality,reader=self.layer_reader,calibration=self.view_calibration)
        previews=all_previews[self.volume_page*4:self.volume_page*4+4] if self.volume_mode=='tiles' else all_previews
        layers=enabled[self.volume_page*4:self.volume_page*4+4] if self.volume_mode=='tiles' else enabled
        shared_range=None
        if self.volume_scale=='shared':
            positive=[p.values[p.values>0] for p in all_previews]
            values=np.concatenate(positive) if positive else np.array([])
            if self.logarithmic:values=np.log1p(values)
            shared_range=(0.,float(np.percentile(values,99.7)) if values.size else 1.)
        constructor=tiled_volume_plot if self.volume_mode=='tiles' else overlay_volume_plot
        fig=constructor(previews,layers,scale_mode=self.volume_scale,stretch=self.display_stretch,log=self.logarithmic,shared_range=shared_range,calibration=self.view_calibration,unit=self.depth_unit)
        display_frames=calibrated_window(frames,self.view_calibration)
        self.volume_details=dict(preview_shape=list(previews[0].values.shape) if previews else [0,0,0],threshold=None,
            layers=fig.layout.meta['layers'],page=self.volume_page,pages=pages,mode=self.volume_mode,voxel_budget=500_000,
            encoded_bytes=len(fig.to_json().encode()),preparation_seconds=perf_counter()-started,
            display_frames=list(display_frames) if display_frames else None,
            omitted_frames=(frames[1]-frames[0]+1)-(display_frames[1]-display_frames[0]+1 if display_frames else 0),
            physical_aspect=bool(fig.layout.meta['physical_aspect']),axis_kind='depth' if self.view_calibration else 'frame')
        return fig

    def custom_recipe(self,payload):
        intervals=payload.get('intervals', [payload['bounds']] if 'bounds' in payload else self.draft_intervals)
        axis=self.meta['masses']
        windows=canonical_intervals(intervals,(float(axis.min()),float(axis.max())))
        recipe=SignalRecipe(source='custom',intervals=windows,frames=tuple(payload.get('frames',self.draft_frames)),
                            label=f'Custom {interval_label(windows)}')
        if recipe.frames[1]>=self.meta['shape'][0]:
            raise ValueError('Integration frame limits must lie within the acquisition.')
        return recipe

    def progress(self,done,total):
        if done%10==0 or done==total:
            self.send(dict(progress=dict(done=done,total=total)))

    def state(self):
        if self.meta is None:
            return dict(loaded=False,revision=self.revision,startup_error=self.startup_error)
        return dict(loaded=True,name=self.meta['name'], path=self.public_path(), shape=list(self.meta['shape']),
                    gib=round(self.meta['bytes']/2**30,2), peaks=self.meta['peaks'],
                    fov=self.meta['fov_um'], raw=self.meta['raw_shape'] is not None,
                    raw_shape=self.meta['raw_shape'], index=self.index, comparisons=self.comparisons, map_projection=self.map_projection,
                    frame=self.frame, frames=self.frames, depth_window=self.depth_window,
                    roi=self.roi, low=self.low, high=self.high, recipe=self.active_recipe.to_dict(),
                    intervals=self.active_recipe.intervals, draft_intervals=self.draft_intervals,
                    draft_windows=[dict(id=r['id'],bounds=list(r['bounds'])) for r in self.draft_windows],
                    selected_interval_id=self.selected_interval_id,
                    draft=self.draft, draft_frames=self.draft_frames, custom=self.custom,
                    label=self.label, log=self.logarithmic, relative=self.relative,
                    percentile=self.percentile, opacity=self.opacity, stretch=self.display_stretch,
                    quality=self.quality, volume_details=getattr(self,'volume_details',None),
                    depth_calibration=self.calibration_metadata(),profile_axis=self.profile_axis,
                    assignments=self.assignments,abundance_rows=self.abundance_rows,abundance_context=self.abundance_context,
                    volume_layers=[dict(id=l.id,recipe=l.recipe.to_dict(),visible=l.visible,colorscale=l.colorscale,opacity=l.opacity,percentile=l.percentile) for l in self.volume_layers],
                    layered_volume=self.layered_volume,volume_mode=self.volume_mode,volume_scale=self.volume_scale,volume_page=self.volume_page,
                    saved_integrations=self.saved_integrations,stale=self.stale,
                    write_enabled=self.settings.allow_writes and self.settings.allow_unverified_native,
                    commercial_status='unverified',
                    revision=self.revision)

    def figures(self, keys=None):
        if self.meta is None:return {}
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
                                      self.comparison_curves(),self.relative,
                                      calibration=self.calibration if self.profile_axis=='depth' else None,unit=self.depth_unit)
                fig.update_layout(dragmode=False, hovermode='x unified')
                fig.layout.shapes[0].update(line=dict(color='#d18c24',width=2),
                                            visible=(not self.map_projection or self.depth_window is not None) and np.isfinite(self.profile_coordinate(self.frame)))
                if self.depth_window:
                    bounds=[self.profile_coordinate(z) for z in self.depth_window]
                    if self.profile_axis=='depth':
                        bounds=[self.profile_coordinate(int(np.clip(z,0,self.calibration.anchors[-1].frame))) for z in self.depth_window]
                    fig.add_vrect(x0=bounds[0],x1=bounds[1],
                                  fillcolor='rgba(209,140,36,.18)',line_color='#d18c24',
                                  line_width=2,editable=False)
            elif key == 'front':
                fig = front_projection(selected_volume,selected_frames,self.roi,self.meta['fov_um'],self.logarithmic,calibration=self.view_calibration,unit=self.depth_unit)
                coordinate=self.profile_coordinate(self.frame)
                fig.add_hline(y=coordinate if np.isfinite(coordinate) else 0,line_color='#d18c24',line_width=1,
                              visible=np.isfinite(coordinate) and (not self.map_projection or self.depth_window is not None))
            elif key in ('xz','yz'):
                fig = cross_section(selected_volume,selected_frames,self.roi,key.upper(),self.meta['fov_um'],self.logarithmic,self.color_max,calibration=self.view_calibration,unit=self.depth_unit)
                coordinate=self.profile_coordinate(self.frame)
                fig.add_hline(y=coordinate if np.isfinite(coordinate) else 0,line_color='#d18c24',line_width=1,
                              visible=np.isfinite(coordinate) and (not self.map_projection or self.depth_window is not None))
            elif key == 'spectrum':
                fig = spectrum_plot(self.meta,intervals=self.draft_intervals,
                                    window_ids=[r['id'] for r in self.draft_windows],selected_id=self.selected_interval_id)
                for c in self.comparisons:
                    for i,(low,high) in enumerate(c['intervals']):
                        fig.add_vrect(x0=low,x1=high,fillcolor=c['color'],opacity=.12,
                                      line=dict(color=c['color'],width=1),layer='below',name=f"comparison:{c['id']}:{i}")
                fig.update_xaxes(rangeslider_visible=False)
                # Spectrum selection is one-dimensional and handled by the
                # widget. Plotly's 2D drawrect leaves zero-height shapes for a
                # horizontal drag and lets trace/shape hit targets intercept it.
                fig.update_layout(dragmode=False)
                fig.update_layout(editrevision=self.revision)
                if self.draft_windows:
                    fig.layout.shapes[0].update(editable=False,fillcolor='rgba(209,140,36,.15)')
            elif key == 'volume':
                if self.layered_volume:
                    fig=self.layered_figure(selected_frames)
                else:
                    fig, preview_shape = volume_plot(selected_volume,selected_frames,self.roi,self.meta['fov_um'],
                                          self.percentile,self.opacity,self.display_stretch,self.logarithmic,self.quality,calibration=self.view_calibration,unit=self.depth_unit)
                    source='Custom integration' if self.custom else self.label
                    x0,x1,y0,y1=self.roi
                    fig.update_layout(title=dict(text=f'3D ion volume · {escape(source)}<br>'
                        f'<sup>Mass {escape(interval_label(self.active_recipe.intervals))} · frames {selected_frames[0]}–{selected_frames[1]} '
                        f'· X {x0}–{x1}, Y {y0}–{y1} px</sup>',font=dict(size=14)),margin=dict(t=66))
                    threshold=None
                    if fig.data and fig.data[0].type=='volume':
                        threshold=float(np.expm1(fig.data[0].isomin) if self.logarithmic else fig.data[0].isomin)
                    self.volume_details=dict(preview_shape=list(preview_shape),threshold=threshold,**fig.layout.meta)
            else:
                continue
            fig.update_layout(autosize=True)
            fig.layout.height = None
            fig.layout.width = None
            fig.update_layout(uirevision=f'{self.meta["path"]}:{key}:{self.profile_axis}:{self.depth_unit}' if key in ('profile','front','xz','yz','volume') else f'{self.meta["path"]}:{key}')
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

    def add_comparison(self,payload):
        index=payload.get('index')
        if index is not None:
            index=int(index)
            if not 0<=index<len(self.meta['peaks']):
                raise ValueError('Unknown comparison channel.')
            recipe=self.stored_recipe(index)
            volume=None
        else:
            recipe=self.custom_recipe(payload)
            volume=None
        for c in self.comparisons:
            other=SignalRecipe.from_dict(c['recipe'])
            if (other.source,other.stored_index,other.intervals,other.frames)==(recipe.source,recipe.stored_index,recipe.intervals,recipe.frames):
                return
        if recipe.source=='custom':
            volume=read_signal(self.meta['path'],recipe,self.progress)
        identifier=self.next_comparison_id
        label=recipe.label
        if recipe.source=='custom':
            from dataclasses import replace
            label+=f' · W{identifier+1} · frames {recipe.frames[0]}–{recipe.frames[1]}'
            recipe=replace(recipe,label=label)
        one=len(recipe.intervals)==1
        descriptor=dict(id=identifier,index=index,label=label,
                        low=recipe.intervals[0][0] if one else None,
                        high=recipe.intervals[0][1] if one else None,
                        intervals=[list(w) for w in recipe.intervals],recipe=recipe.to_dict(),
                        frames=list(recipe.frames),color=comparison_color(identifier))
        if volume is not None:
            self.comparison_volumes[identifier]=volume
        self.comparisons.append(descriptor)
        self.next_comparison_id+=1

    def handle_message(self, widget, content, buffers):
        event=content.get('event')
        try:
            path=self.meta['path'] if self.meta else None
            if event=='open':path=resolve_data_path(self.settings,content.get('payload',{})['path'],require_file=True)
            if path is not None and event not in ('files_list','export'):
                with dataset_lock(path):
                    if event not in ('open','reload_acquisition') and file_identity(path)!=self.loaded_identity:
                        self.stale=True
                        raise ValueError('Acquisition changed in another session. Reload acquisition; export Settings JSON first to retain your analysis recipe.')
                    return self._handle_message(widget,content,buffers)
            return self._handle_message(widget,content,buffers)
        except (ValueError,KeyError,OSError,TypeError) as exc:
            self.send(dict(error=self.safe_error(exc),state=self.state(),figures={},depth_request_id=content.get('payload',{}).get('request_id')))

    def _handle_message(self, widget, content, buffers):
        event = content.get('event')
        p = content.get('payload',{})
        keys = []
        relayout = {}
        try:
            if event=='files_list':
                try:
                    page=list_data_files(self.settings,p.get('path',''),query=p.get('query',''),offset=p.get('offset',0),limit=p.get('limit',100))
                    response=page.to_dict()
                except (ValueError,OSError,TypeError) as exc:
                    response=dict(error=self.safe_error(exc))
                self.send(dict(files=dict(**response,request_id=p.get('request_id'))))
                return
            if self.meta is None and event!='open':
                raise ValueError('Open an acquisition before using analysis controls.')
            if event=='save_preview':
                self.send(dict(save_preview=dict(**self.save_preview(p['recipe_id']),request_id=p.get('request_id'))))
                return
            if event=='save_integration':
                if p['recipe_id']!=self.active_recipe.id or p['expected_identity']!=self.public_identity():
                    raise ValueError('Save preview no longer matches the prepared signal. Review it again.')
                record=self.save_record(p['label'])
                path=self.meta['path']
                result=save_to_acquisition(self.settings,self.public_path(),record,lambda:iter(self.volume),self.loaded_identity)
                saved=dict(id=result.saved_id,backup=str(result.backup.relative_to(self.settings.data_root)),generation=result.generation,warning=result.warning)
                self.stale=True
                try:
                    self.load_file(path);self.select_saved(result.saved_id);self.revision+=1
                    self.volume_layers=[replace(l,recipe=self.active_recipe) if l.id=='active' else l for l in self.volume_layers]
                    figures=self.figures()
                except Exception as exc:
                    self.stale=True;saved['warning']='Saved successfully. Reload acquisition: '+self.safe_error(exc);figures={}
                self.send(dict(saved=saved,state=self.state(),figures=figures))
                return
            if event=='saved_signal':
                self.select_saved(p['saved_id']);keys=None
            elif event=='peak_candidates':
                rows=find_candidates(float(p['mz']),float(p['tolerance']),p['unit'],tuple(p['charges']),load_catalog())
                query=dict(mz=float(p['mz']),tolerance=float(p['tolerance']),unit=p['unit'],charges=p['charges'])
                self.candidate_rows={r.id:dict(id=r.id,**asdict(r),query=query) for r in rows}
                self.send(dict(peak_candidates=dict(rows=list(self.candidate_rows.values()),request_id=p.get('request_id'))))
                return
            elif event=='volume_layer_add':
                recipes=self.available_recipes()
                if p['recipe_id'] not in recipes:raise ValueError('Select a registered active/comparison signal.')
                recipe=recipes[p['recipe_id']]
                if not any(l.recipe.id==recipe.id for l in self.volume_layers):
                    source=next((self.comparison_volumes[c['id']] for c in self.comparisons if c['recipe']['id']==recipe.id and c['id'] in self.comparison_volumes),None)
                    self.layer_sources[recipe.id]=source if source is not None else self.layer_reader(self.meta['path'],recipe)
                    self.volume_layers.append(VolumeLayer(f'layer-{self.next_layer_id}',recipe,colorscale=COLORSCALES[self.next_layer_id%len(COLORSCALES)]))
                    self.next_layer_id+=1
                self.layered_volume=True;keys=['volume']
            elif event=='volume_layer_solo':
                if not any(l.id==p['id'] for l in self.volume_layers):raise ValueError('Unknown volume layer.')
                self.volume_layers=[replace(l,visible=l.id==p['id']) for l in self.volume_layers]
                self.layered_volume=True;keys=['volume']
            elif event in ('volume_layer_remove','volume_layer_style'):
                i=next((i for i,l in enumerate(self.volume_layers) if l.id==p['id']),None)
                if i is None:raise ValueError('Unknown volume layer.')
                if event=='volume_layer_remove':
                    self.volume_layers=[l for l in self.volume_layers if l.id!=p['id']]
                    used={l.recipe.id for l in self.volume_layers};self.layer_sources={k:v for k,v in self.layer_sources.items() if k in used}
                else:
                    changes={k:p[k] for k in ('visible','colorscale','opacity','percentile') if k in p}
                    self.volume_layers[i]=replace(self.volume_layers[i],**changes)
                    if p['id']=='active':self.percentile=self.volume_layers[i].percentile;self.opacity=self.volume_layers[i].opacity
                self.layered_volume=True;keys=['volume']
            elif event=='volume_layout':
                if p['mode'] not in ('tiles','overlay'):raise ValueError('Unknown volume layout.')
                self.volume_mode=p['mode'];self.layered_volume=True;keys=['volume']
            elif event=='volume_scale':
                if p['mode'] not in ('independent','shared'):raise ValueError('Unknown intensity scale.')
                self.volume_scale=p['mode'];self.layered_volume=True;keys=['volume']
            elif event=='volume_page':
                if type(p['page']) is not int or p['page']<0:raise ValueError('Invalid volume page.')
                self.volume_page=p['page'];keys=['volume']
            elif event=='peak_assignment':
                recipes=self.available_recipes()
                if p['recipe_id'] not in recipes:raise ValueError('Select a current signal to annotate.')
                candidate=self.candidate_record(p['candidate_id'])
                self.assignments[p['recipe_id']]=dict(candidate=candidate,original_label=recipes[p['recipe_id']].label)
            elif event=='abundance_measure':
                recipes=self.available_recipes();ids=p['recipe_ids']
                if not ids or len(set(ids))!=len(ids) or any(i not in recipes for i in ids):raise ValueError('Choose distinct current signals to measure.')
                frames=tuple(p.get('frames',self.depth_window or self.frames));roi=tuple(p.get('roi',self.roi))
                if frames[1]>=self.meta['shape'][0]:raise ValueError('Measurement frames exceed the acquisition.')
                measured=measure_isotopes(self.meta['path'],[recipes[i] for i in ids],roi,frames)
                self.abundance_rows=[]
                for row in measured:
                    assignment=self.assignments.get(row.recipe_id,{})
                    isotope=assignment.get('candidate',{}).get('isotope',{})
                    self.abundance_rows.append(dict(**asdict(row),label=recipes[row.recipe_id].label,
                        candidate=assignment.get('candidate'),reference_abundance_low=isotope.get('abundance_low'),reference_abundance_high=isotope.get('abundance_high')))
                self.abundance_context=dict(dataset=self.public_path(),frames=list(frames),roi=list(roi))
            elif event=='abundance_export':
                if not self.abundance_rows:raise ValueError('Measure an isotope set first.')
                out=io.StringIO();writer=csv.writer(out)
                writer.writerow(['recipe_id','signal','atomic_ion','summed_original_intensity','observed_selected_set_fraction','reference_abundance_low','reference_abundance_high','reference_abundance_uncertainty','reference_source_id','mass_error_Th','mass_error_ppm','first_frame','last_frame','requested_first_frame','requested_last_frame','dataset','roi_pixels','status'])
                for row in self.abundance_rows:
                    candidate=row['candidate'] or {};isotope=candidate.get('isotope',{})
                    writer.writerow([row['recipe_id'],row['label'],candidate.get('id',''),row['summed_intensity'],row['observed_fraction'],row['reference_abundance_low'],row['reference_abundance_high'],isotope.get('abundance_uncertainty'),isotope.get('source_id',''),candidate.get('error_Th'),candidate.get('error_ppm'),*(row['actual_frames'] or ('','')),*self.abundance_context['frames'],self.abundance_context['dataset'],json.dumps(self.abundance_context['roi']),row['status']])
                self.send(dict(download=dict(filename='isotope-areas.csv',text=out.getvalue()),state=self.state()));return
            elif event == 'frame':
                self.map_projection = False
                self.frame = int(np.clip(round(float(p['frame'])),*self.frames))
                if self.depth_window:
                    self.depth_window=None
                    self.draft_frames=self.frames
                    keys=['ion','front','se','profile','xz','yz','volume']
                else:
                    keys = ['ion','se']
                    relayout = {'profile':{'shapes[0].x0':self.frame,'shapes[0].x1':self.frame,'shapes[0].visible':True}}
                    coordinate=self.profile_coordinate(self.frame);valid=np.isfinite(coordinate)
                    coordinate=coordinate if valid else 0
                    relayout.update({k:{'shapes[0].y0':coordinate,'shapes[0].y1':coordinate,'shapes[0].visible':bool(valid)} for k in ['xz','yz']})
                    relayout['front']={'shapes[1].y0':coordinate,'shapes[1].y1':coordinate,'shapes[1].visible':bool(valid)}
                    if self.profile_axis=='depth':
                        keys.append('profile');relayout.pop('profile',None)
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
            elif event in ('depth_anchor_set','depth_anchor_remove'):
                frame=p['frame']
                if type(frame) is not int:raise ValueError('Depth anchor frame must be an integer.')
                if frame==0:raise ValueError('Frame 0 is fixed at depth 0.')
                rows=[a for a in self.depth_anchors if a.frame!=frame]
                existing=len(rows)!=len(self.depth_anchors)
                if event=='depth_anchor_set':
                    if existing and not p.get('replace',False):raise ValueError('An anchor already exists at this frame; edit its row.')
                    rows.append(DepthAnchor(frame,float(convert_depth(p['depth'],p['unit'],'nm'))))
                elif not existing:raise ValueError('Unknown depth anchor.')
                rows=validate_anchors(rows,self.meta['shape'][0])
                calibration=DepthCalibration(rows,self.meta['shape'][0]) if len(rows)>=2 else None
                self.depth_anchors=rows;self.calibration=calibration
                if calibration is None:self.profile_axis='frame'
                keys=['profile','front','xz','yz','volume']
            elif event=='depth_unit':
                convert_depth(1,'nm',p['unit']);self.depth_unit='µm' if p['unit']=='um' else p['unit']
                keys=['profile','front','xz','yz','volume']
            elif event=='profile_axis':
                if p['axis'] not in ('frame','depth'):raise ValueError('Unknown profile axis.')
                if p['axis']=='depth' and self.calibration is None:raise ValueError('Add a positive-depth anchor first.')
                self.profile_axis=p['axis'];keys=['profile','front','xz','yz','volume']
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
                self.active_recipe=self.stored_recipe(index)
                self.reset_draft(self.active_recipe.intervals)
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
            elif event in ('window','interval_update'):
                bounds=self.checked_bounds(p['bounds'])
                identifier=p.get('id',self.selected_interval_id)
                if identifier is None and event=='window':
                    self.add_interval(bounds)
                else:
                    self.draft_row(identifier)['bounds']=bounds
                keys=['spectrum']
            elif event == 'interval_add':
                self.add_interval(p.get('bounds'))
                keys=['spectrum']
            elif event == 'interval_select':
                self.draft_row(p['id'])
                self.selected_interval_id=p['id']
                keys=['spectrum']
            elif event == 'interval_remove':
                self.draft_row(p['id'])
                self.draft_windows=[r for r in self.draft_windows if r['id']!=p['id']]
                if self.selected_interval_id==p['id']:
                    self.selected_interval_id=self.draft_windows[0]['id'] if self.draft_windows else None
                keys=['spectrum']
            elif event == 'draft_frames':
                first,last = map(int,p['frames'])
                if not 0 <= first <= last < self.meta['shape'][0]:
                    raise ValueError('Integration frame limits must lie within the acquisition.')
                self.draft_frames = (first,last)
            elif event == 'integrate':
                recipe=self.custom_recipe(p)
                volume=read_signal(self.meta['path'],recipe,self.progress)
                first,last=recipe.frames
                self.volume,self.frames=volume,recipe.frames
                self.active_recipe=recipe
                if self.depth_window:
                    lo,hi=max(first,self.depth_window[0]),min(last,self.depth_window[1])
                    self.depth_window=(lo,hi) if lo<=hi else None
                self.frame=int(np.clip(self.frame,first,last))
                self.reset_draft(recipe.intervals)
                self.draft_frames=recipe.frames
                self.custom=True
                self.set_color_range()
                keys=None
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
                stretch=float(np.clip(float(p.get('stretch',self.display_stretch)),.2,1000 if self.view_calibration else 3))
                if self.view_calibration:self.depth_stretch=stretch
                else:self.stretch=stretch
                self.quality = p.get('quality',self.quality)
                keys = ['ion','front','profile','xz','yz','volume']
            elif event in ('open','reload_acquisition'):
                path=resolve_data_path(self.settings,p['path'],require_file=True) if event=='open' else self.meta['path']
                # Rendering may discover malformed SE or spectrum metadata.
                # Publish nothing until both the load and all figures succeed.
                previous=self.__dict__.copy()
                try:
                    self.load_file(path)
                    self.startup_error=None
                    self.revision+=1
                    prepared=self.figures()
                except Exception:
                    self.__dict__.clear();self.__dict__.update(previous)
                    raise
                self.send(dict(state=self.state(),figures=prepared,relayout={}))
                return
            elif event == 'export':
                self.export(p['format'])
                return
            else:
                raise ValueError('Unknown workspace action.')
            self.revision += 1
            self.volume_layers=[replace(l,recipe=self.active_recipe) if l.id=='active' else l for l in self.volume_layers]
            if event=='display':
                self.volume_layers=[replace(l,percentile=self.percentile,opacity=self.opacity) if l.id=='active' else l for l in self.volume_layers]
            figures = self.figures(keys) if keys is None or keys else {}
            self.send(dict(state=self.state(),figures=figures,relayout=relayout,depth_request_id=p.get('request_id')))
        except (ValueError,KeyError,OSError,TypeError) as exc:
            self.send(dict(error=self.safe_error(exc),state=self.state(),depth_request_id=p.get('request_id'),figures=self.figures(['spectrum'])
                           if event in ('window','interval_add','interval_update','interval_select','interval_remove') else {}))
        except Exception as exc:
            traceback.print_exc()
            self.send(dict(error=f'Unexpected error: {exc}',state=self.state(),depth_request_id=p.get('request_id')))

    def export(self, format):
        selected_frames = self.depth_window or self.frames
        if format == 'csv':
            x0,x1,y0,y1 = self.roi
            selected = self.volume[selected_frames[0]-self.frames[0]:selected_frames[1]-self.frames[0]+1]
            profile = selected[:,y0:y1+1,x0:x1+1].mean(axis=(1,2),dtype=np.float64)
            out = io.StringIO()
            writer = csv.writer(out)
            curves = self.comparison_curves()
            writer.writerow(['frame',*(['depth_nm'] if self.calibration else []),'roi_mean_intensity',*[f"{c['label']} [comparison {c['id']+1}]" for c in self.comparisons]])
            for i,z in enumerate(range(selected_frames[0],selected_frames[1]+1)):
                offset = z-self.frames[0]
                depth=self.calibration.frame_to_depth(z) if self.calibration else None
                writer.writerow([z,*([f'{float(depth):.9g}' if np.isfinite(depth) else ''] if self.calibration else []),f'{profile[i]:.9g}',*[f'{c[1][offset]:.9g}' if np.isfinite(c[1][offset]) else '' for c in curves]])
            filename,text = 'depth-profile.csv',out.getvalue()
        else:
            recipe=self.active_recipe.to_dict()
            recipe.update(dataset=self.public_path(),signal=self.label,frames_inclusive=selected_frames,
                          loaded_frames_inclusive=self.frames,roi_pixels_inclusive=self.roi,
                          z_units='frame',fov_um=self.meta['fov_um'],comparisons=self.comparisons)
            recipe.update(depth_calibration=self.calibration_metadata(),profile_axis=self.profile_axis)
            display_frames=calibrated_window(selected_frames,self.view_calibration)
            recipe.update(display_z_units=self.depth_unit if self.view_calibration else 'frame',
                          z_display_stretch=self.display_stretch,physical_aspect=bool(self.view_calibration and self.meta['fov_um'] and display_frames and display_frames[1]>display_frames[0]))
            recipe.update(assignments=self.assignments,abundance_rows=self.abundance_rows,abundance_context=self.abundance_context)
            recipe.update(volume_layers=self.state()['volume_layers'],volume_mode=self.volume_mode,volume_scale=self.volume_scale)
            if len(self.active_recipe.intervals)==1:
                recipe.update(lower_Th=self.low,upper_Th=self.high)
            filename,text = 'mass-window.json',json.dumps(recipe,indent=2)
        self.send(dict(download=dict(filename=filename,text=text),state=self.state()))
