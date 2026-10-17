// Offline candidate display. Only explicit analysis actions reconstruct events.
function abundance(record) {
  if(record?.abundance_low==null)return 'Unknown';
  const lo=record.abundance_low*100,hi=record.abundance_high*100;
  const text=lo===hi?`${lo.toPrecision(5)}%`:`${lo.toPrecision(5)}–${hi.toPrecision(5)}%`;
  return text+(record.abundance_uncertainty!=null?` ± ${(record.abundance_uncertainty*100).toPrecision(2)}%`:'');
}
function cell(row,text){const td=document.createElement('td');td.textContent=text;row.append(td);return td;}
export function mountPeakHelper(dialog,tableRoot,{send,apply,compare}) {
  dialog.innerHTML=`<h3 id="peak-helper-title">Atomic-ion helper</h3><div class="tof-depth-options">
    <label>Measured m/z<input type="number" step="any" aria-label="Measured mass"></label>
    <label>Tolerance<input type="number" min="0" step="any" value=".02" aria-label="Mass tolerance"></label>
    <label>Units<select aria-label="Mass tolerance unit"><option>Th</option><option>ppm</option></select></label>
    <label>Polarity<select aria-label="Ion polarity"><option value="1">Positive</option><option value="-1">Negative</option></select></label>
    <label>Charge<select aria-label="Ion charge"><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="all">1–3</option></select></label></div>
    <button type="button" data-find>Find candidates</button><p class="tof-candidate-status" aria-live="polite"></p>
    <div class="tof-reference-table"><table><thead><tr><th>Atomic ion</th><th>Predicted m/z</th><th>Error (Th / ppm)</th><th>Reference abundance</th><th></th></tr></thead><tbody></tbody></table></div>
    <div class="tof-depth-options"><label>Signal annotation<select aria-label="Signal to annotate"></select></label><button type="button" data-annotate disabled>Annotate signal</button></div>
    <div class="tof-depth-options"><label>Lower Th<input type="number" step="any" aria-label="Candidate window lower"></label><label>Upper Th<input type="number" step="any" aria-label="Candidate window upper"></label><button type="button" data-apply disabled>Apply window</button><button type="button" data-compare disabled>Add as comparison</button></div>
    <p>Atomic ions only, charges ±1–3. Suggestions preserve file labels. Binding-energy corrections are omitted. Natural reference abundances do not establish sample composition.</p><p role="alert"></p>
    <div class="tof-files-actions"><button type="button" data-done>Done</button></div>`;
  dialog.setAttribute('aria-labelledby','peak-helper-title');
  tableRoot.innerHTML=`<div class="tof-subtoolbar"><button type="button" data-measure>Measure selected signals</button><button type="button" data-export disabled>Isotope CSV ↓</button></div><div class="tof-measure-choices"></div><p class="tof-measure-context"></p>
    <div class="tof-reference-table"><table><thead><tr><th>Signal / ion</th><th>Original intensity sum</th><th>Observed selected-set fraction</th><th>Reference abundance</th><th>Covered frames</th><th>Status</th></tr></thead><tbody></tbody></table></div>
    <p class="tof-hint">Fractions describe the measured isotope set, not atomic concentrations. Overlapping windows suppress fractions; comparisons use common frame coverage.</p>`;
  const $=s=>dialog.querySelector(s),t=s=>tableRoot.querySelector(s);
  let state,selected=null,requestId=0,pending=false,dataset=null;const checked=new Map();
  const input=name=>$(`[aria-label="${name}"]`);
  function candidateRequest() {
    selected=null;for(const key of ['annotate','apply','compare'])$(`[data-${key}]`).disabled=true;
    const sign=Number(input('Ion polarity').value),charge=input('Ion charge').value;
    $('.tof-candidate-status').textContent='Finding candidates…';$('[role=alert]').textContent='';
    send('peak_candidates',{mz:Number(input('Measured mass').value),tolerance:Number(input('Mass tolerance').value),unit:input('Mass tolerance unit').value,charges:(charge==='all'?[1,2,3]:[Number(charge)]).map(z=>z*sign),request_id:++requestId});
  }
  $('[data-find]').addEventListener('click',candidateRequest);
  $('[data-annotate]').addEventListener('click',()=>{pending=true;send('peak_assignment',{recipe_id:input('Signal to annotate').value,candidate_id:selected.id});});
  function windowRecipe(){return {intervals:[[Number(input('Candidate window lower').value),Number(input('Candidate window upper').value)]],frames:state.draft_frames};}
  $('[data-apply]').addEventListener('click',()=>{apply(windowRecipe());dialog.close();});
  $('[data-compare]').addEventListener('click',()=>{compare(windowRecipe());dialog.close();});
  $('[data-done]').addEventListener('click',()=>dialog.close());
  function dismiss(e){if(e.key==='Escape'){e.preventDefault();e.stopPropagation();dialog.close();}}
  dialog.addEventListener('keydown',dismiss,true);
  t('[data-measure]').addEventListener('click',()=>send('abundance_measure',{recipe_ids:[...checked].filter(([,enabled])=>enabled).map(([id])=>id),frames:state.depth_window||state.frames,roi:state.roi}));
  t('[data-export]').addEventListener('click',()=>send('abundance_export'));
  return {
    show(){input('Measured mass').value=state.draft?(state.draft[0]+state.draft[1])/2:state.peaks[state.index].mass;dialog.showModal();},
    candidates(response){
      if(response.request_id!==requestId)return;
      const body=$('tbody');body.replaceChildren();$('.tof-candidate-status').textContent=response.rows.length?`${response.rows.length} possible atomic ions`:'No candidates within tolerance';
      for(const candidate of response.rows) {
        const row=document.createElement('tr');row.dataset.candidate=candidate.id;
        cell(row,candidate.id+(candidate.isotope.mass_estimated?' (estimated mass)':''));cell(row,candidate.predicted_mz.toFixed(7));cell(row,`${candidate.error_Th.toPrecision(4)} / ${candidate.error_ppm.toPrecision(4)}`);cell(row,abundance(candidate.isotope));
        row.title=candidate.isotope.source_id;
        const select=document.createElement('button');select.type='button';select.textContent='Select';select.addEventListener('click',()=>{
          selected=candidate;for(const r of body.children)r.setAttribute('aria-selected',String(r===row));
          const tolerance=Number(input('Mass tolerance').value),half=input('Mass tolerance unit').value==='ppm'?candidate.predicted_mz*tolerance/1e6:tolerance;
          input('Candidate window lower').value=candidate.predicted_mz-half;input('Candidate window upper').value=candidate.predicted_mz+half;
          $('[data-annotate]').disabled=false;for(const key of ['apply','compare'])$(`[data-${key}]`).disabled=!state.raw;
        });cell(row,'').append(select);body.append(row);
      }
    },
    sync(next,error){state=next;if(next.loaded===false)return;
      if(dataset!==next.path){
        dataset=next.path;checked.clear();selected=null;pending=false;requestId++;
        $('tbody').replaceChildren();$('[role=alert]').textContent='';$('.tof-candidate-status').textContent='';
        for(const key of ['annotate','apply','compare'])$(`[data-${key}]`).disabled=true;
        input('Candidate window lower').value='';input('Candidate window upper').value='';
      }
      if(pending){$('[role=alert]').textContent=error||'Annotation saved; original label retained.';pending=false;}
      const signals=[next.recipe,...next.comparisons.map(c=>c.recipe)],unique=[...new Map(signals.map(r=>[r.id,r])).values()];
      for(const id of checked.keys())if(!unique.some(r=>r.id===id))checked.delete(id);
      const previous=input('Signal to annotate').value;input('Signal to annotate').replaceChildren();t('.tof-measure-choices').replaceChildren();
      for(const recipe of unique) {
        const opt=document.createElement('option');opt.value=recipe.id;opt.textContent=recipe.label;input('Signal to annotate').append(opt);
        if(!checked.has(recipe.id))checked.set(recipe.id,true);
        const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=checked.get(recipe.id);check.addEventListener('change',()=>checked.set(recipe.id,check.checked));
        label.append(check,document.createTextNode(recipe.label));t('.tof-measure-choices').append(label);
      }
      if(unique.some(r=>r.id===previous))input('Signal to annotate').value=previous;
      const body=t('tbody');body.replaceChildren();
      for(const row of next.abundance_rows) {
        const tr=document.createElement('tr');tr.dataset.measurementRow=row.recipe_id;
        cell(tr,row.label+(row.candidate?` / ${row.candidate.id}`:''));cell(tr,row.summed_intensity==null?'Unavailable':row.summed_intensity.toPrecision(7));cell(tr,row.observed_fraction==null?'Unavailable':`${(row.observed_fraction*100).toPrecision(5)}%`);cell(tr,abundance(row.candidate?.isotope));cell(tr,row.actual_frames?row.actual_frames.join('–'):'None');cell(tr,row.status);body.append(tr);
      }
      t('[data-export]').disabled=!next.abundance_rows.length;
      const c=next.abundance_context;t('.tof-measure-context').textContent=c?`Measured ${c.dataset} · requested frames ${c.frames.join('–')} · ROI ${c.roi.join(', ')} px`:'Select signals and measure using the current frame window and spatial ROI.';
    },
    error(message){$('[role=alert]').textContent=message;$('.tof-candidate-status').textContent='Candidate search failed';},
    dispose(){dialog.removeEventListener('keydown',dismiss,true);dialog.replaceChildren();tableRoot.replaceChildren();}
  };
}
