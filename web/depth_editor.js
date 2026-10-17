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
export function mountDepthEditor(root,{send,createPlot,getFigure}) {
  root.innerHTML=`<h3 id="depth-title">Known depths</h3>
    <div class="tof-dialog-plot-toolbar"><span>Click a profile position, then enter its known depth. Drag to zoom.</span><button type="button" data-full>All frames</button></div>
    <div class="tof-dialog-plot" data-dialog-plot="depth" role="region" aria-label="Interactive calibration profiles"></div>
    <div class="tof-depth-options tof-anchor-entry"><label>Selected frame<input type="number" min="0" step="1" aria-label="Anchor frame"></label><label>Known depth<input type="number" min="0" step="any" aria-label="Known depth"></label><button type="button" data-add>Add anchor</button></div>
    <p data-selection-note>Click a profile to choose a frame.</p>
    <div class="tof-depth-options">
    <label>Depth coordinates<select aria-label="Depth coordinates"><option value="frame">Frames</option><option value="depth">Physical depth</option></select></label>
    <label>Depth display unit<select aria-label="Depth display unit"><option>nm</option><option>µm</option><option>mm</option></select></label></div>
    <div class="tof-anchor-table"><table><thead><tr><th>Frame</th><th>Depth</th><th></th></tr></thead><tbody></tbody></table></div>
    <p class="tof-depth-span"></p><p role="alert"></p><div class="tof-files-actions"><button type="button" data-done>Done</button></div>`;
  root.setAttribute('aria-labelledby','depth-title');const $=s=>root.querySelector(s);
  let state=null,unit='nm',newDepth=null,dataset=null,selectedFrame=null,requestId=0,draftVersion=0;
  const edits=new Map(),pending=new Map();
  const frameInput=$('[aria-label="Anchor frame"]'),depthInput=$('[aria-label="Known depth"]');
  const graph=createPlot?.($('[data-dialog-plot]'),{getFigure,prepare(figure){
    for(const trace of figure.data){trace.x=trace.customdata;trace.hovertemplate='Frame=%{x}<br>Signal=%{y:.5g}<extra>%{fullData.name}</extra>';}
    figure.layout.title={text:'Current channels · click to assign a known depth',font:{size:14}};
    figure.layout.margin={l:60,r:20,t:75,b:45};figure.layout.uirevision=`depth-editor:${dataset}`;figure.layout.dragmode='zoom';
    figure.layout.xaxis={...figure.layout.xaxis,title:{text:'Depth frame'},autorange:true};delete figure.layout.xaxis.range;
    figure.layout.shapes=[];figure.layout.annotations=[];
    for(const anchor of state.depth_calibration.anchors){
      if(anchor.frame<state.frames[0] || anchor.frame>state.frames[1])continue;
      figure.layout.shapes.push({type:'line',xref:'x',yref:'paper',x0:anchor.frame,x1:anchor.frame,y0:0,y1:1,line:{color:'#d18c24',dash:'dot',width:1}});
      figure.layout.annotations.push({xref:'x',yref:'paper',x:anchor.frame,y:1,yanchor:'top',showarrow:false,font:{size:10,color:'#ac7c25'},text:`${anchor.depth_nm/scales[unit]} ${unit}`});
    }
    if(selectedFrame!==null && selectedFrame>=state.frames[0] && selectedFrame<=state.frames[1])figure.layout.shapes.push({type:'line',xref:'x',yref:'paper',x0:selectedFrame,x1:selectedFrame,y0:0,y1:1,line:{color:'#6355c7',width:2}});
  },onPick(value){chooseFrame(Math.max(state.frames[0],Math.min(state.frames[1],Math.round(value))));depthInput.focus();},onError(message){$('[role=alert]').textContent=message;}});
  function selectionControls(){
    const existing=state.depth_calibration.anchors.some(a=>a.frame===selectedFrame);
    depthInput.disabled=selectedFrame===0;$('[data-add]').disabled=selectedFrame===0;
    $('[data-add]').textContent=existing && selectedFrame!==0?'Update anchor':'Add anchor';
    $('[data-selection-note]').textContent=selectedFrame===0?'Frame 0 is fixed at depth 0.':selectedFrame===null?'Click a profile to choose a frame.':`Frame ${selectedFrame} selected · ${existing?'edit its known depth':'enter a known depth'} (${unit})`;
  }
  function chooseFrame(frame){
    draftVersion++;
    selectedFrame=frame;frameInput.value=frame;
    const anchor=state.depth_calibration.anchors.find(a=>a.frame===frame);
    newDepth=anchor?.depth_nm??null;depthInput.value=newDepth===null?'':newDepth/scales[unit];
    $('[role=alert]').textContent='';selectionControls();void graph?.refresh();
  }
  frameInput.addEventListener('change',()=>{if(frameInput.value===''){selectedFrame=null;selectionControls();return;}chooseFrame(Number(frameInput.value));});
  $('[data-full]').addEventListener('click',()=>graph?.reset());
  function submit(event,payload){const id=++requestId;pending.set(id,{event,payload,draftVersion});$('[role=alert]').textContent='';send(event,{...payload,request_id:id});}
  $('[aria-label="Known depth"]').addEventListener('input',e=>{draftVersion++;newDepth=e.target.value===''?null:Number(e.target.value)*scales[unit];});
  $('[data-add]').addEventListener('click',()=>{
    const frame=$('[aria-label="Anchor frame"]'),depth=$('[aria-label="Known depth"]');
    if(!frame.value || !depth.value){$('[role=alert]').textContent='Enter a frame and known depth.';return;}
    const frameNumber=Number(frame.value),replace=state.depth_calibration.anchors.some(a=>a.frame===frameNumber);
    submit('depth_anchor_set',{frame:frameNumber,depth:Number(depth.value),unit,replace});
  });
  $('[aria-label="Depth display unit"]').addEventListener('change',e=>submit('depth_unit',{unit:e.target.value}));
  $('[aria-label="Depth coordinates"]').addEventListener('change',e=>submit('profile_axis',{axis:e.target.value}));
  $('[data-done]').addEventListener('click',()=>root.close());
  function dismiss(e){if(e.key==='Escape'){e.preventDefault();e.stopPropagation();root.close();}}
  root.addEventListener('keydown',dismiss,true);
  return {show(){draftVersion++;root.showModal();selectedFrame=state.frame>0?state.frame:null;frameInput.value=selectedFrame??'';depthInput.value='';newDepth=null;selectionControls();return graph?.refresh();},
    refreshPlot(){return graph?.refresh();},
    sync(next,error,responseId){state=next;if(next.loaded===false)return;
      if(dataset!==next.path){dataset=next.path;edits.clear();newDepth=null;pending.clear();selectedFrame=null;draftVersion++;}
      const acknowledged=pending.get(responseId);
      if(acknowledged){
        if(responseId===requestId)$('[role=alert]').textContent=error || '';
        if(!error && acknowledged.event==='depth_anchor_set') {
          const p=acknowledged.payload;
          if(edits.get(p.frame)===p.depth*scales[p.unit])edits.delete(p.frame);
          if(draftVersion===acknowledged.draftVersion && Number(frameInput.value)===p.frame)newDepth=state.depth_calibration.anchors.find(a=>a.frame===p.frame)?.depth_nm??null;
        }
        pending.delete(responseId);
      }
      const c=state.depth_calibration,body=$('tbody');body.replaceChildren();unit=c.unit;
      if(newDepth!==null)$('[aria-label="Known depth"]').value=newDepth/scales[unit];
      $('[aria-label="Depth display unit"]').value=c.unit;$('[aria-label="Depth coordinates"]').value=state.profile_axis;
      $('[aria-label="Depth coordinates"] option[value=depth]').disabled=c.anchors.length<2;
      $('[aria-label="Anchor frame"]').max=state.shape[0]-1;
      selectionControls();
      for(const anchor of c.anchors) {
        const row=document.createElement('tr');row.dataset.anchorFrame=anchor.frame;
        const frame=document.createElement('td');frame.textContent=anchor.frame;
        const depth=document.createElement('td'),controls=document.createElement('td');
        if(anchor.frame===0){depth.textContent=`0 ${c.unit}`;controls.textContent='Fixed';}
        else {
          const input=document.createElement('input');input.type='number';input.step='any';input.value=(edits.get(anchor.frame)??anchor.depth_nm)/scales[c.unit];input.setAttribute('aria-label',`Depth at frame ${anchor.frame}`);
          input.addEventListener('input',()=>edits.set(anchor.frame,Number(input.value)*scales[unit]));
          const edit=document.createElement('button');edit.type='button';edit.textContent='Update';
          edit.addEventListener('click',()=>submit('depth_anchor_set',{frame:anchor.frame,depth:Number(input.value),unit:c.unit,replace:true}));
          const remove=document.createElement('button');remove.type='button';remove.textContent='×';remove.setAttribute('aria-label','Remove anchor');
          remove.addEventListener('click',()=>submit('depth_anchor_remove',{frame:anchor.frame}));depth.append(input);controls.append(edit,remove);
        }
        row.append(frame,depth,controls);body.append(row);
      }
      $('.tof-depth-span').textContent=c.anchors.length<2?'Add a positive-depth anchor. Frame 0 stays at depth 0.':`Applies to profiles, front projection, cross-sections and 3D. Calibrated frames 0–${c.anchors.at(-1).frame}; later depths are unknown and omitted in physical views. Intensities and frame selections are unchanged.`;
    },dispose(){graph?.dispose();root.removeEventListener('keydown',dismiss,true);root.replaceChildren();}};
}
