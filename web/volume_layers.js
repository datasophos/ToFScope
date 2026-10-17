const maps=['Viridis','Magma','Plasma','Cividis','Reds','Blues','Greens','Purples'];
const intervals=recipe=>recipe.intervals.map(([a,b])=>`${a.toFixed(4)}–${b.toFixed(4)}`).join(' ∪ ')+' Th';
export function mountVolumeLayers(root,{send,getPlot}) {
  root.innerHTML=`<h3 id="layers-title">3D layers</h3><div class="tof-depth-options"><label>Arrangement<select aria-label="3D arrangement"><option value="tiles">Tiled</option><option value="overlay">Overlay</option></select></label><label>Intensity scales<select aria-label="3D intensity scales"><option value="independent">Independent</option><option value="shared">Shared numerical range</option></select></label><label class="tof-check"><input type="checkbox" checked aria-label="Link tile cameras">Link cameras</label></div>
    <div class="tof-depth-options"><label>Active / comparison signal<select aria-label="Signal for 3D layer"></select></label><button type="button" data-add>Add layer</button></div>
    <div class="tof-layer-list"></div><div class="tof-files-pages"><button type="button" data-prev>Previous tiles</button><span data-page></span><button type="button" data-next>Next tiles</button></div>
    <p>Each layer integrates its own mass intervals. Depth and spatial ROI follow the explorer; unknown coverage stays missing. Overlay transparency is qualitative; use tiled views to inspect obscured layers.</p><p role="alert"></p><div class="tof-files-actions"><button type="button" data-done>Done</button></div>`;
  root.setAttribute('aria-labelledby','layers-title');const $=s=>root.querySelector(s);
  let state,gd=null,applying=false,dataset=null,linked=true;const cameras=new Map();
  function sceneLayers(){
    if(!state?.layered_volume)return [['scene','active']];
    const rows=state.volume_details?.layers || [];
    return state.volume_mode==='overlay'?[['scene','overlay']]:rows.map((row,i)=>[i?`scene${i+1}`:'scene',row.id]);
  }
  async function relayout(patch){if(!gd || !Object.keys(patch).length)return;applying=true;try{await window.Plotly.relayout(gd,patch);}finally{applying=false;}}
  function onCamera(event) {
    if(applying)return;
    const scenes=sceneLayers();
    for(const [scene,id] of scenes) {
      const key=`${scene}.camera`;
      if(!event[key])continue;
      const camera=event[key];cameras.set(id,camera);
      if(linked && state.volume_mode==='tiles') {
        const patch={};for(const [other,otherId] of scenes)if(other!==scene){cameras.set(otherId,camera);patch[`${other}.camera`]=camera;}
        void relayout(patch);
      }
      break;
    }
  }
  $('[aria-label="3D arrangement"]').addEventListener('change',e=>send('volume_layout',{mode:e.target.value}));
  $('[aria-label="3D intensity scales"]').addEventListener('change',e=>send('volume_scale',{mode:e.target.value}));
  $('[aria-label="Link tile cameras"]').addEventListener('change',e=>{linked=e.target.checked;});
  $('[data-add]').addEventListener('click',()=>send('volume_layer_add',{recipe_id:$('[aria-label="Signal for 3D layer"]').value}));
  $('[data-prev]').addEventListener('click',()=>send('volume_page',{page:state.volume_page-1}));
  $('[data-next]').addEventListener('click',()=>send('volume_page',{page:state.volume_page+1}));
  $('[data-done]').addEventListener('click',()=>root.close());
  function dismiss(e){if(e.key==='Escape'){e.preventDefault();e.stopPropagation();root.close();}}
  root.addEventListener('keydown',dismiss,true);
  return {show(){root.showModal();},
    update(next,error){state=next;if(next.loaded===false)return;
      if(dataset!==next.path){dataset=next.path;cameras.clear();}
      $('[role=alert]').textContent=error||'';$('[aria-label="3D arrangement"]').value=next.volume_mode;$('[aria-label="3D intensity scales"]').value=next.volume_scale;
      const chooser=$('[aria-label="Signal for 3D layer"]'),previous=chooser.value;chooser.replaceChildren();
      const recipes=[next.recipe,...next.comparisons.map(c=>c.recipe)],choices=[...new Map(recipes.map(r=>[r.id,r])).values()].filter(r=>!next.volume_layers.some(l=>l.recipe.id===r.id));
      for(const recipe of choices){const option=document.createElement('option');option.value=recipe.id;option.textContent=recipe.label;chooser.append(option);}
      if(choices.some(r=>r.id===previous))chooser.value=previous;$('[data-add]').disabled=!choices.length;
      const list=$('.tof-layer-list');list.replaceChildren();
      for(const layer of next.volume_layers) {
        const row=document.createElement('section');row.dataset.layerId=layer.id;row.className='tof-layer-row';
        const heading=document.createElement('strong');heading.textContent=layer.recipe.label;
        const details=document.createElement('small');details.textContent=`Mass ${intervals(layer.recipe)} · recipe frames ${layer.recipe.frames.join('–')}`;
        const preview=next.volume_details?.layers?.find(p=>p.id===layer.id);
        if(preview)details.textContent+=` · preview ${preview.shape.join(' × ')} · ${next.volume_scale} scale ${preview.scale_min}–${Number(preview.scale_max).toPrecision(4)} ${next.log?'log(1+I)':'intensity'}`;
        row.append(heading,details);const controls=document.createElement('div');controls.className='tof-depth-options';
        function label(text,input){const l=document.createElement('label');l.append(document.createTextNode(text),input);controls.append(l);}
        const visible=document.createElement('input');visible.type='checkbox';visible.checked=layer.visible;visible.setAttribute('aria-label','Show layer');visible.addEventListener('change',()=>send('volume_layer_style',{id:layer.id,visible:visible.checked}));label('Show',visible);
        const scale=document.createElement('select');scale.setAttribute('aria-label','Layer colormap');
        for(const name of maps){const option=document.createElement('option');option.value=option.textContent=name;scale.append(option);}scale.value=layer.colorscale;
        scale.addEventListener('change',()=>send('volume_layer_style',{id:layer.id,colorscale:scale.value}));label('Colormap',scale);
        for(const [key,title,min,max,step] of [['opacity','Layer opacity',0,1,.01],['percentile','Layer percentile',0,100,1]]) {
          const input=document.createElement('input');input.type='number';input.min=min;input.max=max;input.step=step;input.value=layer[key];input.setAttribute('aria-label',title);
          input.addEventListener('change',()=>send('volume_layer_style',{id:layer.id,[key]:Number(input.value)}));label(key==='percentile'?'Hide below percentile':'Opacity',input);
        }
        const solo=document.createElement('button');solo.type='button';solo.textContent='Solo';solo.addEventListener('click',()=>send('volume_layer_solo',{id:layer.id}));controls.append(solo);
        const remove=document.createElement('button');remove.type='button';remove.textContent='×';remove.setAttribute('aria-label','Remove layer');remove.addEventListener('click',()=>send('volume_layer_remove',{id:layer.id}));controls.append(remove);row.append(controls);list.append(row);
      }
      const pages=next.volume_details?.pages || 1;$('[data-page]').textContent=next.volume_mode==='tiles'?`Page ${next.volume_page+1} / ${pages}`:'All enabled layers';
      $('[data-prev]').disabled=next.volume_mode!=='tiles'||next.volume_page===0;$('[data-next]').disabled=next.volume_mode!=='tiles'||next.volume_page+1>=pages;
    },
    async attach(){
      const plot=getPlot();if(!plot?.on)return;
      if(gd!==plot){if(gd)gd.removeListener('plotly_relayout',onCamera);gd=plot;gd.on('plotly_relayout',onCamera);}
      const patch={};for(const [scene,id] of sceneLayers())if(cameras.has(id)&&JSON.stringify(gd.layout[scene]?.camera)!==JSON.stringify(cameras.get(id)))patch[`${scene}.camera`]=cameras.get(id);
      await relayout(patch);
    },
    dispose(){if(gd)gd.removeListener('plotly_relayout',onCamera);root.removeEventListener('keydown',dismiss,true);root.replaceChildren();}
  };
}
