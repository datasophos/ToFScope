from dataclasses import replace
import json
from tofscope.application.commands import CommandEnvelope,AllDepth
from tofscope.application.models import DisplaySettings
from tofscope.application.workspaces import Conflict
from tofscope.science.signals import SignalRecipe

class ExploreService:
    def __init__(self,workspaces,repository):self.workspaces=workspaces;self.repository=repository
    def stored(self,s,index):
        if not 0<=index<len(s.peaks):raise ValueError('Unknown stored channel.')
        p=s.peaks[index];return SignalRecipe(label=p.label,source='stored',stored_index=index,intervals=((p.low,p.high),),frames=s.loaded_frames)
    def validate_envelope(self,e,envelope,fingerprint):
        s=e.snapshot
        if e.closed:raise KeyError('Analysis unavailable.')
        if envelope.request_id in e.receipts:
            old,result=e.receipts[envelope.request_id]
            if old!=fingerprint:raise Conflict('Request ID reused with different content.',s.revision)
            return result
        if envelope.expected_revision!=s.revision:raise Conflict('Analysis revision changed.',s.revision)
        if envelope.dataset_generation!=s.dataset.generation:raise Conflict('Acquisition generation changed.',s.revision)
        self.repository.assert_current(s.owner,s.dataset)
        return None
    def receipt(self,e,request_id,fingerprint,result):
        e.receipts[request_id]=(fingerprint,result)
        while len(e.receipts)>256:e.receipts.popitem(last=False)
    def apply(self,owner,analysis_id,envelope):
        if not isinstance(envelope,CommandEnvelope):envelope=CommandEnvelope(**envelope)
        fingerprint=envelope.model_dump_json();e=self.workspaces.entry(owner,analysis_id)
        with e.lock:
            previous=self.validate_envelope(e,envelope,fingerprint)
            if previous is not None:return previous
            s=e.snapshot;c=envelope.command;kind=c.type;patch={}
            if kind=='select_stored':patch['active_recipe']=self.stored(s,c.index)
            elif kind=='set_roi':
                x0,x1,y0,y1=c.roi
                if not 0<=x0<=x1<s.shape[2] or not 0<=y0<=y1<s.shape[1]:raise ValueError('ROI outside pixel domain.')
                patch['roi']=tuple(c.roi)
            elif kind=='set_depth':
                d=c.depth;first,last=s.loaded_frames
                if d.mode=='frame' and not first<=d.index<=last:raise ValueError('Frame outside loaded range.')
                if d.mode=='window' and not first<=d.first<=d.last<=last:raise ValueError('Window outside loaded range.')
                patch['depth']=d
            elif kind=='set_loaded_frames':
                first,last=c.frames
                if not 0<=first<=last<s.shape[0]:raise ValueError('Loaded frames outside acquisition.')
                patch=dict(loaded_frames=tuple(c.frames),depth=AllDepth())
                if s.active_recipe.source=='stored':patch['active_recipe']=replace(s.active_recipe,frames=tuple(c.frames))
            elif kind=='add_stored_comparison':patch['comparisons']=s.comparisons+(self.stored(s,c.index),)
            elif kind=='remove_comparison':
                if not any(r.id==c.recipe_id for r in s.comparisons):raise ValueError('Unknown comparison.')
                patch['comparisons']=tuple(r for r in s.comparisons if r.id!=c.recipe_id)
            elif kind=='set_display':patch['display']=DisplaySettings(c.log,c.relative,c.image)
            result=replace(s,revision=s.revision+1,**patch)
            if kind in ('select_stored','set_loaded_frames'):e.tokens['active']+=1
            if kind=='set_loaded_frames':e.tokens['comparison']+=1
            if kind=='select_stored' and s.active_recipe.id in e.leases:e.leases.pop(s.active_recipe.id).release()
            if kind=='remove_comparison' and c.recipe_id in e.leases:e.leases.pop(c.recipe_id).release()
            e.snapshot=result;self.receipt(e,envelope.request_id,fingerprint,result);return result
