// Piecewise coordinates for gestures only; never resample measured intensities.
const scales={nm:1,'µm':1000,um:1000,mm:1e6};
function interpolate(value,anchors,key,result) {
  if(value<anchors[0][key] || value>anchors.at(-1)[key])return NaN;
  for(let i=1;i<anchors.length;i++)if(value<=anchors[i][key]) {
    const a=anchors[i-1],b=anchors[i];return a[result]+(value-a[key])*(b[result]-a[result])/(b[key]-a[key]);
  }
  return NaN;
}
export function profileToFrame(value,state) {
  if(state.profile_axis!=='depth')return value;
  const c=state.depth_calibration;return interpolate(value*scales[c.unit],c.anchors,'depth_nm','frame');
}
export function frameToProfile(value,state) {
  if(state.profile_axis!=='depth')return value;
  const c=state.depth_calibration;return interpolate(value,c.anchors,'frame','depth_nm')/scales[c.unit];
}
export function mountDepthEditor(root,{send}) {
  root.innerHTML=`<h3 id="depth-title">Known depths</h3><div class="tof-depth-options">
    <label>Profile coordinates<select aria-label="Profile coordinates"><option value="frame">Frames</option><option value="depth">Physical depth</option></select></label>
    <label>Depth display unit<select aria-label="Depth display unit"><option>nm</option><option>µm</option><option>mm</option></select></label></div>
    <table><thead><tr><th>Frame</th><th>Depth</th><th></th></tr></thead><tbody></tbody></table>
    <div class="tof-depth-options"><label>Frame<input type="number" min="1" step="1" aria-label="Anchor frame"></label><label>Known depth<input type="number" min="0" step="any" aria-label="Known depth"></label><button type="button" data-add>Add anchor</button></div>
    <p class="tof-depth-span"></p><p role="alert"></p><div class="tof-files-actions"><button type="button" data-done>Done</button></div>`;
  root.setAttribute('aria-labelledby','depth-title');const $=s=>root.querySelector(s);
  let state=null,pending=false;
  function submit(event,payload){pending=true;$('[role=alert]').textContent='';send(event,payload);}
  $('[data-add]').addEventListener('click',()=>{
    const frame=$('[aria-label="Anchor frame"]'),depth=$('[aria-label="Known depth"]');
    if(!frame.value || !depth.value){$('[role=alert]').textContent='Enter a frame and known depth.';return;}
    submit('depth_anchor_set',{frame:Number(frame.value),depth:Number(depth.value),unit:state.depth_calibration.unit});
  });
  $('[aria-label="Depth display unit"]').addEventListener('change',e=>submit('depth_unit',{unit:e.target.value}));
  $('[aria-label="Profile coordinates"]').addEventListener('change',e=>submit('profile_axis',{axis:e.target.value}));
  $('[data-done]').addEventListener('click',()=>root.close());
  function dismiss(e){if(e.key==='Escape'){e.preventDefault();e.stopPropagation();root.close();}}
  root.addEventListener('keydown',dismiss,true);
  return {show(){root.showModal();$('[aria-label="Anchor frame"]').value=state.frame>0?state.frame:'';$('[aria-label="Known depth"]').value='';},
    sync(next,error){state=next;if(next.loaded===false)return;
      if(pending){$('[role=alert]').textContent=error || '';pending=false;}
      const c=state.depth_calibration,body=$('tbody');body.replaceChildren();
      $('[aria-label="Depth display unit"]').value=c.unit;$('[aria-label="Profile coordinates"]').value=state.profile_axis;
      $('[aria-label="Profile coordinates"] option[value=depth]').disabled=c.anchors.length<2;
      $('[aria-label="Anchor frame"]').max=state.shape[0]-1;
      for(const anchor of c.anchors) {
        const row=document.createElement('tr');row.dataset.anchorFrame=anchor.frame;
        const frame=document.createElement('td');frame.textContent=anchor.frame;
        const depth=document.createElement('td'),controls=document.createElement('td');
        if(anchor.frame===0){depth.textContent=`0 ${c.unit}`;controls.textContent='Fixed';}
        else {
          const input=document.createElement('input');input.type='number';input.step='any';input.value=anchor.depth_nm/scales[c.unit];input.setAttribute('aria-label',`Depth at frame ${anchor.frame}`);
          const edit=document.createElement('button');edit.type='button';edit.textContent='Update';
          edit.addEventListener('click',()=>submit('depth_anchor_set',{frame:anchor.frame,depth:Number(input.value),unit:c.unit,replace:true}));
          const remove=document.createElement('button');remove.type='button';remove.textContent='×';remove.setAttribute('aria-label','Remove anchor');
          remove.addEventListener('click',()=>submit('depth_anchor_remove',{frame:anchor.frame}));depth.append(input);controls.append(edit,remove);
        }
        row.append(frame,depth,controls);body.append(row);
      }
      $('.tof-depth-span').textContent=c.anchors.length<2?'Add a positive-depth anchor. Frame 0 stays at depth 0.':`Calibrated frames 0–${c.anchors.at(-1).frame}. Linear interpolation between anchors; later depths are unknown.`;
    },dispose(){root.removeEventListener('keydown',dismiss,true);root.replaceChildren();}};
}
