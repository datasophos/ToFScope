// Explicit writes only. Merely opening or cancelling this dialog never saves.
export function mountSaveIntegration(root,{send}) {
  root.innerHTML=`<h3 id="save-title">Save integration</h3>
    <p data-save-summary>Preparing review…</p>
    <p>Commercial TOFexplorer compatibility: <strong>unverified</strong>. A backup is retained before replacement.</p>
    <label>Native peak label<input type="text" aria-label="Native peak label" maxlength="63"></label>
    <p>Full XY scientific values are saved. The displayed ROI, log colors and preview sampling are not applied.</p>
    <p role="alert"></p><div class="tof-files-actions"><button type="button" data-cancel>Cancel</button><button type="button" class="tof-primary" data-save disabled>Save to acquisition</button></div>`;
  root.setAttribute('aria-labelledby','save-title');
  const $=s=>root.querySelector(s),button=$('[data-save]'),cancel=$('[data-cancel]'),label=$('input'),alert=$('[role=alert]');
  let state=null,preview=null,saving=false,requestId=0;
  function check(){button.disabled=saving || !preview?.can_save || !/^[\x20-\x7e]{1,63}$/.test(label.value);}
  function sync(next){state=next;if(root.open && !saving && preview && preview.recipe_id!==state.recipe?.id){preview=null;check();alert.textContent='The active signal changed. Close and review the save again.';}}
  function show(){
    if(!state?.loaded)return;
    preview=null;saving=false;button.hidden=false;cancel.textContent='Cancel';cancel.disabled=false;label.disabled=true;label.value='';
    alert.textContent='';$('[data-save-summary]').textContent='Preparing review…';check();root.showModal();
    send('save_preview',{recipe_id:state.recipe.id,request_id:++requestId});
  }
  function reviewed(value){
    if(!root.open || value.request_id!==requestId)return;
    preview=value;label.value=value.label;label.disabled=false;
    $('[data-save-summary]').textContent=`${value.target} · ${value.intervals.map(w=>w.map(x=>x.toFixed(4)).join('–')).join(' ∪ ')} Th · frames ${value.frames.join('–')} · ${value.spatial_shape.join(' × ')} pixels · requires ${(value.required_bytes/2**20).toFixed(1)} MiB free`;
    alert.textContent=value.reason || '';check();
  }
  function error(message){if(!root.open)return;saving=false;cancel.disabled=false;label.disabled=false;alert.textContent=message;check();}
  function saved(value){
    if(!root.open)return;saving=false;button.hidden=true;cancel.disabled=false;cancel.textContent='Close';label.disabled=true;preview=null;
    $('[data-save-summary]').textContent=`Saved successfully. Backup: ${value.backup}`;
    alert.textContent=value.warning || '';
  }
  button.addEventListener('click',()=>{
    if(button.disabled)return;saving=true;check();cancel.disabled=true;label.disabled=true;
    $('[data-save-summary]').textContent='Saving and verifying full-resolution data…';
    send('save_integration',{recipe_id:preview.recipe_id,label:label.value,expected_identity:preview.expected_identity});
  });
  label.addEventListener('input',check);cancel.addEventListener('click',()=>root.close());
  const prevent=e=>{if(saving)e.preventDefault();};root.addEventListener('cancel',prevent);
  return {sync,show,reviewed,error,saved,dispose(){root.removeEventListener('cancel',prevent);}};
}
