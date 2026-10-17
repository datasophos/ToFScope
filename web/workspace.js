const tabs = {slices: ['ion','front','se','spectrum','profile'], sections: ['xz','yz'], spectrum: ['spectrum'], volume: ['volume']};

async function render({ model, el }) {
  // Use the installed Plotly bundle: no CDN or data upload is required.
  if (!window.Plotly) {
    const script = document.createElement('script');
    script.textContent = model.get('plotly_js');
    document.head.appendChild(script);
  }
  const Plotly = window.Plotly;
  const moduleURL=URL.createObjectURL(new Blob([model.get('interval_editor_js')],{type:'text/javascript'}));
  let intervalModule;
  try {intervalModule=await import(moduleURL);} finally {URL.revokeObjectURL(moduleURL);}
  const {mountIntervalEditor,formatIntervals,sameIntervals}=intervalModule;
  const filesURL=URL.createObjectURL(new Blob([model.get('file_browser_js')],{type:'text/javascript'}));
  let mountFileBrowser;
  try {({mountFileBrowser}=await import(filesURL));} finally {URL.revokeObjectURL(filesURL);}
  const depthURL=URL.createObjectURL(new Blob([model.get('depth_editor_js')],{type:'text/javascript'}));
  let mountDepthEditor,profileToFrame,frameToProfile;
  try {({mountDepthEditor,profileToFrame,frameToProfile}=await import(depthURL));} finally {URL.revokeObjectURL(depthURL);}
  const initial = model.get('initial');
  let state = initial.state;
  const figures = {...initial.figures};
  const dirty = new Set(Object.keys(figures));
  const updating = new Set();
  const mounted = new Set();
  let active = 'slices';
  let imageMode = 'sims';
  let focusedDisplay = null;
  let disposed = false;
  let rendering = Promise.resolve();
  let datasetPath = '';
  el.classList.add('tof-host');
  // Published Marimo cells are the app shell; edit-mode cells keep their normal
  // notebook output so the workspace never covers the source editor.
  for(let ancestor=el;ancestor;ancestor=ancestor.parentElement || ancestor.getRootNode()?.host) {
    if(ancestor.classList?.contains('marimo-cell')) {
      el.classList.toggle('tof-viewport',ancestor.classList.contains('published'));
      break;
    }
  }
  el.innerHTML = `
    <div class="tof-app">
      <header class="tof-header">
        <div class="tof-brand"><span class="tof-mark">T<span>·</span></span><div><strong>ToFScope</strong><small>FIB–SEM / TOF–SIMS</small></div></div>
        <div class="tof-file"><strong data-field="filename"></strong><small data-field="dimensions"></small></div>
        <button data-action="open-dialog" class="tof-quiet">Open file</button>
        <button data-action="export-csv" class="tof-quiet">Profile CSV ↓</button>
        <button data-action="export-json" class="tof-quiet">Settings JSON ↓</button>
      </header>
      <div class="tof-body">
        <aside class="tof-sidebar">
          <div class="tof-caption">SIGNAL</div>
          <div class="tof-picker" data-picker="peak">
            <div class="tof-picker-label">Ion channel</div>
            <button type="button" class="tof-picker-trigger" data-picker-trigger="peak" aria-label="Choose ion channel" aria-haspopup="dialog" aria-expanded="false"><span data-picker-value="peak"></span><span aria-hidden="true">⌕</span></button>
            <div class="tof-picker-recent" data-picker-recent="peak"></div>
            <div class="tof-picker-popup" data-picker-popup="peak" role="dialog" aria-label="Choose ion channel" hidden>
              <input type="search" role="combobox" data-picker-search="peak" aria-label="Search ion channels" aria-autocomplete="list" aria-expanded="true" placeholder="Mass or label · 27, Pt" autocomplete="off">
              <div class="tof-picker-count" data-picker-count="peak" aria-live="polite"></div>
              <div class="tof-picker-results" data-picker-results="peak" role="listbox" aria-label="Matching ion channels"></div>
            </div>
          </div>
          <div class="tof-picker" data-picker="comparison">
            <div class="tof-picker-label">Comparison profiles <span data-field="comparison-count"></span></div>
            <div class="tof-picker-control"><button type="button" class="tof-picker-trigger" data-picker-trigger="comparison" aria-label="Add comparison channel" aria-haspopup="dialog" aria-expanded="false"><span data-picker-value="comparison"></span><span aria-hidden="true">⌕</span></button></div>
            <div class="tof-picker-recent" data-picker-recent="comparison"></div>
            <div class="tof-picker-popup" data-picker-popup="comparison" role="dialog" aria-label="Add comparison channel" hidden>
              <input type="search" role="combobox" data-picker-search="comparison" aria-label="Search comparison channels" aria-autocomplete="list" aria-expanded="true" placeholder="Mass or label · 48, Pt" autocomplete="off">
              <div class="tof-picker-count" data-picker-count="comparison" aria-live="polite"></div>
              <div class="tof-picker-results" data-picker-results="comparison" role="listbox" aria-label="Matching comparison channels"></div>
            </div>
          </div>
          <div class="tof-comparison-list" data-field="comparison-list" aria-label="Comparison windows"></div>
          <button data-action="comparison-clear" class="tof-quiet tof-full" hidden>Clear comparisons</button>
          <div class="tof-source"><span data-field="source"></span><strong data-field="signal"></strong></div>
          <label class="tof-check"><input type="checkbox" data-input="log"> Log ion colors</label>
          <label class="tof-check"><input type="checkbox" data-input="relative"> Relative profiles</label>
          <div class="tof-divider"></div>
          <div class="tof-caption">MASS WINDOWS <span class="tof-draft" data-field="draft-tag">DRAFT</span></div>
          <p class="tof-help">Draw to edit the selected interval, or enter exact limits. Add intervals to combine separated peaks.</p>
          <div class="tof-interval-list" data-field="interval-list" aria-label="Draft integration intervals"></div>
          <button data-action="interval-add" class="tof-quiet tof-full">Add interval</button>
          <div class="tof-pair">
            <label>Lower (Th)<input type="number" step="0.001" data-input="low" aria-label="Lower mass limit"></label>
            <label>Upper (Th)<input type="number" step="0.001" data-input="high" aria-label="Upper mass limit"></label>
          </div>
          <div class="tof-pair">
            <label>First frame<input type="number" step="1" min="0" data-input="first" aria-label="First integration frame"></label>
            <label>Last frame<input type="number" step="1" min="0" data-input="last" aria-label="Last integration frame"></label>
          </div>
          <button data-action="integrate" class="tof-primary">Apply custom window</button>
          <button data-action="comparison-window" class="tof-quiet tof-full">Add window to comparisons</button>
          <p class="tof-help">Comparisons use the mass and frame limits above; the active image signal stays selected.</p>
          <button data-action="stored" class="tof-quiet tof-full">Restore stored channel</button>
          <div class="tof-divider"></div>
          <div class="tof-caption">SPATIAL REGION</div>
          <p class="tof-help">Draw on the ion map. Click the gold outline to reveal its edit handles, then drag to move or resize.</p>
          <div class="tof-roi" data-field="roi"></div>
          <button data-action="reset-roi" class="tof-quiet tof-full">Reset to full field</button>
          <details class="tof-details"><summary>Exact pixel limits</summary>
            <div class="tof-pair"><label>X first<input type="number" data-input="x0" aria-label="ROI X first"></label><label>X last<input type="number" data-input="x1" aria-label="ROI X last"></label></div>
            <div class="tof-pair"><label>Y first<input type="number" data-input="y0" aria-label="ROI Y first"></label><label>Y last<input type="number" data-input="y1" aria-label="ROI Y last"></label></div>
            <button data-action="roi-exact" class="tof-quiet tof-full">Set region</button>
          </details>
        </aside>
        <main class="tof-main">
          <div class="tof-toolbar">
            <nav class="tof-tabs" role="tablist" aria-label="Explorer views">
              <button role="tab" data-tab="slices" aria-selected="true">Explore</button>
              <button role="tab" data-tab="sections" aria-selected="false">Cross-sections</button>
              <button role="tab" data-tab="spectrum" aria-selected="false">Mass spectrum</button>
              <button role="tab" data-tab="volume" aria-selected="false">3D volume</button>
            </nav>
            <div class="tof-frame-nav"><button data-action="all-depths" class="tof-all-depths" aria-pressed="true" title="Show all loaded depths">All depths</button><button data-action="prev" aria-label="Previous frame">‹</button><label>Frame <input type="number" data-input="frame" aria-label="Depth frame"></label><button data-action="next" aria-label="Next frame">›</button></div>
          </div>
          <div class="tof-panel" data-panel="slices" role="tabpanel" aria-label="Images, spectrum and profiles">
            <div class="tof-explore-grid">
              <section class="tof-image-pane" aria-label="Acquisition images">
                <div class="tof-image-switch" role="group" aria-label="Image source">
                  <button data-image-mode="sims" aria-pressed="true">SIMS images</button>
                  <button data-image-mode="se" aria-pressed="false">FIB SE image</button>
                  <span class="tof-help-tip"><button class="tof-info" aria-label="Image help">i</button><span role="tooltip" data-field="image-note">Draw on the top map to select a spatial ROI. Front projection sums Y within that ROI.</span></span>
                </div>
                <div class="tof-sims-stack" data-image-content="sims">
                  <div class="tof-plot" data-plot="ion"></div>
                  <div class="tof-plot" data-plot="front"></div>
                </div>
                <div class="tof-plot tof-se-view" data-image-content="se" data-plot="se" hidden></div>
              </section>
              <section class="tof-analysis-stack" aria-label="Spectrum and depth profile">
                <div class="tof-spectrum-home"></div>
                <div class="tof-profile-view">
                  <span class="tof-sr-only" data-field="depth-note" aria-live="polite"></span>
                  <div class="tof-plot tof-profile" data-plot="profile"></div>
                </div>
              </section>
            </div>
          </div>
          <div class="tof-panel" data-panel="sections" role="tabpanel" aria-label="Cross-sections" hidden>
            <div class="tof-section-grid"><div class="tof-plot" data-plot="xz"></div><div class="tof-plot" data-plot="yz"></div></div>
          </div>
          <div class="tof-panel" data-panel="spectrum" role="tabpanel" aria-label="Mass spectrum" hidden>
            <div class="tof-spectrum-view">
            <div class="tof-subtoolbar"><button data-action="draw-window" class="tof-quiet">Draw window</button><button data-action="zoom-window" class="tof-quiet">Zoom to window</button><button data-action="zoom-spectrum" class="tof-quiet">Show full spectrum</button><span data-field="window-note"></span></div>
            <div class="tof-plot tof-spectrum" data-plot="spectrum"></div>
            </div>
          </div>
          <div class="tof-panel" data-panel="volume" role="tabpanel" aria-label="3D volume" hidden>
            <div class="tof-volume-context" aria-label="3D data selection">
              <div class="tof-volume-strip">
                <span><small>Mass</small> <strong data-field="volume-mass"></strong></span>
                <span><small>Depth</small> <strong data-field="volume-depth"></strong></span>
                <span><small>ROI</small> <strong data-field="volume-roi"></strong></span>
              </div>
              <details class="tof-volume-details">
                <summary>Data &amp; preview details</summary>
                <div class="tof-volume-context-grid">
                  <div><small>MASS INTEGRATION</small><strong data-field="volume-source"></strong><span data-field="volume-ion"></span><button data-action="volume-edit-mass" class="tof-quiet">Edit on spectrum →</button></div>
                  <div><small>DEPTH WINDOW</small><span>Each frame remains a separate layer</span><button data-action="volume-edit-region" class="tof-quiet">Select on profile →</button></div>
                  <div><small>SPATIAL ROI</small><span data-field="volume-roi-size"></span><button data-action="volume-edit-roi" class="tof-quiet">Draw on ion map →</button></div>
                  <div><small>DISPLAY PREVIEW</small><strong data-field="volume-preview"></strong><span data-field="volume-threshold"></span></div>
                </div>
                <p>Same active ion as the ion map. The ion map sums the selected depth layers; this view keeps them in 3D. Comparison channels and relative scaling apply to the profile chart. Rendering controls change appearance only.</p>
              </details>
            </div>
            <div class="tof-volume-pending" data-field="volume-pending" hidden></div>
            <div class="tof-volume-options">
              <label>Hide below percentile<input type="number" min="0" max="99" step="1" data-input="percentile" aria-label="3D lower percentile"></label>
              <label>Opacity<input type="number" min="0.02" max="0.4" step="0.02" data-input="opacity" aria-label="3D opacity"></label>
              <label>Z display stretch<input type="number" min="0.2" max="3" step="0.1" data-input="stretch" aria-label="Z display stretch"></label>
              <label>Preview quality<select data-input="quality" aria-label="3D preview quality"><option>Fast</option><option>Detailed</option></select></label>
            </div>
            <div class="tof-plot tof-volume" data-plot="volume"></div>
          </div>
          <section class="tof-focus-pane" aria-label="Maximized display" hidden>
            <div class="tof-focus-bar"><strong data-field="focus-title"></strong><button data-action="restore-display" aria-label="Restore layout">↙ Restore layout <small>Esc</small></button></div>
            <div class="tof-focus-body"></div>
          </section>
        </main>
      </div>
      <footer class="tof-status"><span data-field="status" role="status">Loading workspace…</span><span data-field="selection-summary"></span><span>LOCAL · READ ONLY</span></footer>
      <dialog class="tof-dialog"></dialog>
      <dialog class="tof-dialog tof-depth-dialog"></dialog>
    </div>`;
  const $ = (selector) => el.querySelector(selector);
  const input = (name) => $(`[data-input="${name}"]`);
  const plot = (name) => $(`[data-plot="${name}"]`);
  const field = (name) => $(`[data-field="${name}"]`);
  const number = (name) => Number(input(name).value);
  let pendingOpen=false;
  const fileBrowser=mountFileBrowser($('.tof-dialog'),{
    requestPage:payload=>send('files_list',payload),
    openFile:path=>{pendingOpen=true;send('open',{path});}
  });
  const depthEditor=mountDepthEditor($('.tof-depth-dialog'),{send});
  const intervalEditor=mountIntervalEditor(field('interval-list'),{send,onSelect(row){
    // Keep the field values paired with the optimistic selection even when
    // Apply is clicked before the server acknowledges the selected row.
    input('low').value=row.bounds[0];input('high').value=row.bounds[1];
  }});
  function selectedDraft() {
    return state.draft_windows.find(r=>r.id===intervalEditor.selectedId())?.bounds || state.draft;
  }
  function draftPayload() {
    const selected=intervalEditor.selectedId();
    const intervals=state.draft_windows.map(row=>row.id===selected?[number('low'),number('high')]:[...row.bounds]);
    return {intervals,frames:[number('first'),number('last')]};
  }
  const displayNames={ion:'SIMS top map',front:'SIMS front projection',se:'FIB SE image',spectrum:'Mass spectrum',profile:'Depth profile',xz:'XZ cross-section',yz:'YZ cross-section',volume:'3D volume'};
  const displayHelp={
    ion:'Draw a rectangle on this map to select a spatial ROI. Click the gold outline to reveal its edit handles, then drag to move or resize it.',
    front:'This XZ projection sums the selected spatial ROI’s Y rows. Click to select a depth frame.',
    se:'SE images are paired by index and shown in native pixels. A selected depth window shows their unregistered mean; registration and timing alignment are unverified.',
    spectrum:'Drag horizontally to select a mass window. Drag gold edges to resize; Shift-drag to move. Apply custom window for images, or Add window to comparisons for another profile. Limits are inclusive; raw reconstruction can differ slightly from vendor processing.',
    profile:'Click for one frame; drag to integrate a depth window. Drag edges to resize; Shift-drag to move. Each curve is the mean signal within the spatial ROI. Relative profiles scales each curve to its own maximum.',
    xz:'A section through the center Y of the spatial ROI. Click to select a depth frame.',
    yz:'A section through the center X of the spatial ROI. Click to select a depth frame.',
    volume:'Drag to rotate; scroll to zoom. Preview voxels are block means. Z is acquisition frames; stretch is arbitrary, not a calibrated physical depth. Profiles and exports retain original resolution.'
  };
  const helpPrefix=`help-${Math.random().toString(36).slice(2)}`;
  for(const [key,label] of Object.entries(displayNames)) {
    const gd=plot(key),frame=document.createElement('div');
    frame.className='tof-display';frame.dataset.display=key;
    if(gd.dataset.imageContent){frame.dataset.imageContent=gd.dataset.imageContent;frame.hidden=gd.hidden;gd.hidden=false;delete gd.dataset.imageContent;}
    gd.replaceWith(frame);frame.append(gd);
    const tools=document.createElement('div');tools.className='tof-display-tools';
    const tip=document.createElement('span');tip.className='tof-help-tip';
    const info=document.createElement('button');info.type='button';info.className='tof-info';info.textContent='i';info.setAttribute('aria-label',`${label} help`);
    const help=document.createElement('span');help.setAttribute('role','tooltip');help.textContent=displayHelp[key];help.id=`${helpPrefix}-${key}`;info.setAttribute('aria-describedby',help.id);tip.append(info,help);
    const maximize=document.createElement('button');maximize.type='button';maximize.className='tof-maximize';maximize.textContent='⤢';maximize.title=`Maximize ${label.toLowerCase()}`;maximize.setAttribute('aria-label',maximize.title);
    maximize.addEventListener('click',()=>maximizeDisplay(key));
    if(key==='profile') {
      const calibrate=document.createElement('button');calibrate.type='button';calibrate.className='tof-clear-depth';calibrate.textContent='Depth…';calibrate.dataset.action='calibrate-depth';calibrate.setAttribute('aria-label','Calibrate depth');tools.append(calibrate);
      const clear=document.createElement('button');clear.type='button';clear.className='tof-clear-depth';clear.textContent='All depths';clear.dataset.action='clear-depth';clear.title='Show all loaded depths';clear.setAttribute('aria-label','Clear depth window');tools.append(clear);
    }
    tools.append(tip,maximize);frame.append(tools);
  }
  field('image-note').id=`${helpPrefix}-images`;$('.tof-image-switch .tof-info').setAttribute('aria-describedby',field('image-note').id);
  $('.tof-spectrum-home').append($('.tof-spectrum-view'));
  function status(text, error=false) { field('status').textContent = text; field('status').classList.toggle('tof-error',error); }
  function send(event,payload={}) { if(event==='files_list'){model.send({event,payload});return;} status(event==='integrate'||(event==='comparison_add'&&(payload.bounds||payload.intervals))?'Reconstructing raw events…':'Updating…'); model.send({event,payload}); }
  function setInput(name,value) {
    let focused=document.activeElement;
    while(focused?.shadowRoot?.activeElement) focused=focused.shadowRoot.activeElement;
    if(focused!==input(name)) input(name).value=value;
  }
  const pickerPrefix=`tof-${Math.random().toString(36).slice(2)}`;
  const pickers={};
  function createPicker(name) {
    const root=$(`[data-picker="${name}"]`), trigger=$(`[data-picker-trigger="${name}"]`);
    const popup=$(`[data-picker-popup="${name}"]`), search=$(`[data-picker-search="${name}"]`);
    const list=$(`[data-picker-results="${name}"]`), count=$(`[data-picker-count="${name}"]`);
    const recent=$(`[data-picker-recent="${name}"]`), value=$(`[data-picker-value="${name}"]`);
    let selected=null, history=[], matches=[], highlighted=0;
    list.id=`${pickerPrefix}-${name}-results`;
    search.setAttribute('aria-controls',list.id);
    trigger.setAttribute('aria-controls',`${pickerPrefix}-${name}-popup`);
    popup.id=`${pickerPrefix}-${name}-popup`;
    const title=(p)=>`${p.mass.toFixed(4)} Th · ${p.label}`;
    function close(focus=false) {
      popup.hidden=true;trigger.setAttribute('aria-expanded','false');
      search.removeAttribute('aria-activedescendant');
      if(focus) trigger.focus();
    }
    function choose(index) {close(true);send(name==='peak'?'peak':'comparison_add',{index});}
    function drawResults() {
      const query=search.value.trim().toLowerCase();
      const numeric=query!=='' && /^\d+(?:\.\d*)?$/.test(query)?Number(query):null;
      let all=state.peaks.filter(p=>!query || p.label.toLowerCase().includes(query)
        || (numeric===null?p.mass.toFixed(4).includes(query)
          :p.mass.toFixed(4).startsWith(query) || Math.abs(p.mass-numeric)<=.5));
      const center=numeric??state.peaks.find(p=>p.index===selected)?.mass??state.peaks[state.index].mass;
      if(numeric!==null || !query) all.sort((a,b)=>Math.abs(a.mass-center)-Math.abs(b.mass-center) || a.mass-b.mass);
      matches=all.slice(0,8);
      highlighted=Math.max(0,Math.min(highlighted,matches.length-1));
      list.replaceChildren();
      count.textContent=matches.length?`${query?`${all.length} match${all.length===1?'':'es'}`:'Nearby channels'}${all.length>8?' · showing 8; type to narrow':''}`:'No matching stored channels';
      for(const [i,p] of matches.entries()) {
        const option=document.createElement('button');option.type='button';option.className='tof-picker-option';
        option.id=`${pickerPrefix}-${name}-option-${p.index}`;
        option.setAttribute('role','option');option.setAttribute('aria-selected',String(p.index===selected));
        option.tabIndex=-1;option.classList.toggle('tof-highlighted',i===highlighted);
        const heading=document.createElement('span');heading.className='tof-picker-option-title';
        heading.textContent=title(p);
        const limits=document.createElement('small');limits.textContent=`${p.low.toFixed(4)}–${p.high.toFixed(4)} Th`;
        option.append(heading,limits);
        option.addEventListener('pointerdown',e=>e.preventDefault());
        option.addEventListener('click',()=>choose(p.index));
        list.append(option);
      }
      if(matches.length) search.setAttribute('aria-activedescendant',`${pickerPrefix}-${name}-option-${matches[highlighted].index}`);
      else search.removeAttribute('aria-activedescendant');
    }
    function open() {
      Object.values(pickers).forEach(p=>p.close());
      popup.hidden=false;trigger.setAttribute('aria-expanded','true');
      search.value='';highlighted=0;drawResults();search.focus();
    }
    trigger.addEventListener('click',()=>popup.hidden?open():close());
    trigger.addEventListener('keydown',e=>{if(e.key==='ArrowDown'){e.preventDefault();open();}});
    search.addEventListener('input',()=>{highlighted=0;drawResults();});
    search.addEventListener('keydown',e=>{
      if(e.key==='Escape'){e.preventDefault();close(true);}
      else if(e.key==='Tab') close();
      else if(e.key==='ArrowDown' || e.key==='ArrowUp') {
        e.preventDefault();if(!matches.length)return;
        highlighted=(highlighted+(e.key==='ArrowDown'?1:-1)+matches.length)%matches.length;
        drawResults();list.children[highlighted]?.scrollIntoView({block:'nearest'});
      } else if(e.key==='Enter') {e.preventDefault();if(matches.length)choose(matches[highlighted].index);}
    });
    return {root,close,reset(){selected=null;history=[];close();},sync(index){
      if(index!==selected) {
        selected=index;
        if(index>=0) history=[index,...history.filter(v=>v!==index)].slice(0,5);
      }
      const p=state.peaks.find(p=>p.index===index);
      value.textContent=name==='comparison'?'+ Add stored channel':p?title(p):'Choose channel';trigger.title=value.textContent;
      recent.replaceChildren();
      const others=history.filter(v=>v!==index);
      if(others.length) {
        const label=document.createElement('small');label.textContent='Recent';recent.append(label);
        for(const v of others) {
          const peak=state.peaks.find(p=>p.index===v);if(!peak)continue;
          const button=document.createElement('button');button.type='button';
          button.textContent=peak.mass.toFixed(2);button.title=title(peak);
          button.setAttribute('aria-label',`Use recent ${peak.mass.toFixed(4)} Th`);
          button.addEventListener('click',()=>choose(v));recent.append(button);
        }
      }
      if(!popup.hidden) drawResults();
    }};
  }
  pickers.peak=createPicker('peak');pickers.comparison=createPicker('comparison');
  function closePickers(e) {for(const picker of Object.values(pickers))if(!e.composedPath().includes(picker.root))picker.close();}
  document.addEventListener('pointerdown',closePickers);
  function syncState(next,error=null) {
    state = next;
    depthEditor.sync(state,error);
    const loaded=state.loaded!==false;
    $('.tof-body').hidden=!loaded;
    for(const name of ['export-csv','export-json']) $(`[data-action="${name}"]`).disabled=!loaded;
    $('.tof-app').dataset.revision=state.revision;
    if(!loaded) {
      field('filename').textContent='No acquisition open';field('filename').title='';
      field('dimensions').textContent='Open a file from the server data directory';
      field('selection-summary').textContent='';return;
    }
    if (datasetPath !== state.path) {
      Object.values(pickers).forEach(p=>p.reset());
      datasetPath = state.path;
    }
    field('filename').textContent = state.name;
    field('filename').title = state.path;
    field('dimensions').textContent = `${state.shape[0].toLocaleString()} frames · ${state.shape[2]} × ${state.shape[1]} pixels · ${state.shape[3]} channels · ${state.gib} GiB`;
    field('signal').textContent = state.label;
    field('source').textContent = state.custom?'RECONSTRUCTED RAW EVENTS':'STORED PEAK CHANNEL';
    const draftChanged = !sameIntervals(state.draft_intervals,state.intervals);
    intervalEditor.sync(state);
    const displayedFrames=state.depth_window || state.frames;
    const draftFramesChanged=state.draft_frames[0]!==displayedFrames[0] || state.draft_frames[1]!==displayedFrames[1];
    field('volume-source').textContent=state.custom?'Applied custom integration':'Stored channel from file';
    field('volume-mass').textContent=formatIntervals(state.intervals);
    field('volume-ion').textContent=state.label;
    field('volume-depth').textContent=`Frames ${displayedFrames[0]}–${displayedFrames[1]} · ${displayedFrames[1]-displayedFrames[0]+1} layers`;
    field('volume-roi').textContent=`X ${state.roi[0]}–${state.roi[1]} · Y ${state.roi[2]}–${state.roi[3]} px`;
    const nx=state.roi[1]-state.roi[0]+1,ny=state.roi[3]-state.roi[2]+1;
    field('volume-roi-size').textContent=state.fov?`${(nx*state.fov/state.shape[2]).toFixed(2)} × ${(ny*state.fov/state.shape[1]).toFixed(2)} µm`:`${nx} × ${ny} pixels`;
    const details=state.volume_details;
    field('volume-preview').textContent=details?`${details.preview_shape.join(' × ')} · ${state.log?'log colors':'linear colors'}`:'Block-averaged intensity';
    field('volume-threshold').textContent=details?.threshold!==null && details?.threshold!==undefined?`${state.percentile}th percentile of nonzero preview voxels · ≥ ${details.threshold.toPrecision(3)} intensity`:'Preview averages spatial and depth blocks';
    field('volume-pending').hidden=!(draftChanged || draftFramesChanged);
    field('volume-pending').textContent=`Pending custom integration: ${formatIntervals(state.draft_intervals)}, frames ${state.draft_frames[0]}–${state.draft_frames[1]}. Press Apply custom window to update the volume. The active-data summary above describes what is currently rendered.`;
    field('draft-tag').textContent = draftChanged?'DRAFT':'WINDOW';
    field('window-note').textContent = `${formatIntervals(state.draft_intervals)}${draftChanged?' · draft, not applied':''}`;
    field('roi').textContent = `X ${state.roi[0]}–${state.roi[1]} · Y ${state.roi[2]}–${state.roi[3]} px`;
    field('selection-summary').textContent = state.depth_window?`Integrated frames ${state.depth_window[0]}–${state.depth_window[1]} · Ion sum / SE mean`:state.map_projection?`All loaded depths · frames ${state.frames[0]}–${state.frames[1]} · ${state.custom?'Custom window':'Stored channel'}`:`Frame ${state.frame} / ${state.frames[0]}–${state.frames[1]} · ${state.custom?'Custom window':'Stored channel'}`;
    $('[data-action="clear-depth"]').hidden=!state.depth_window && state.map_projection;
    $('[data-action="all-depths"]').setAttribute('aria-pressed',String(!state.depth_window && state.map_projection));
    field('depth-note').textContent = state.depth_window?`Selected depth: ${state.depth_window[0]}–${state.depth_window[1]}`:'Full depth';
    pickers.peak.sync(state.index);pickers.comparison.sync(-1);
    field('comparison-count').textContent=state.comparisons.length?`(${state.comparisons.length})`:'';
    field('comparison-list').replaceChildren();
    for(const c of state.comparisons) {
      const row=document.createElement('div');row.className='tof-comparison-row';
      row.style.setProperty('--curve-color',c.color);
      const text=document.createElement('div'), label=document.createElement('strong'), limits=document.createElement('small');
      label.textContent=c.label;
      limits.textContent=`${formatIntervals(c.intervals)} · frames ${c.frames[0]}–${c.frames[1]}`;
      text.append(label,limits);
      const remove=document.createElement('button');remove.type='button';remove.textContent='×';
      remove.setAttribute('aria-label',`Remove comparison ${c.label}`);
      remove.addEventListener('click',()=>send('comparison_remove',{id:c.id}));
      row.append(text,remove);field('comparison-list').append(row);
    }
    $('[data-action="comparison-clear"]').hidden=!state.comparisons.length;
    $('[data-action="comparison-window"]').disabled=!state.raw || !state.draft_windows.length;
    setInput('frame',state.frame);
    input('frame').min=state.frames[0]; input('frame').max=state.frames[1];
    setInput('low',state.draft?state.draft[0]:''); setInput('high',state.draft?state.draft[1]:'');
    input('low').disabled=input('high').disabled=!state.draft;
    $('[data-action="zoom-window"]').disabled=!state.draft;
    setInput('first',state.draft_frames[0]); setInput('last',state.draft_frames[1]);
    for (const name of ['first','last']) input(name).max=state.shape[0]-1;
    for (const [i,name] of ['x0','x1','y0','y1'].entries()) setInput(name,state.roi[i]);
    for (const name of ['percentile','opacity','stretch','quality']) setInput(name,state[name]);
    for (const name of ['log','relative']) input(name).checked=state[name];
    $('[data-action="integrate"]').disabled=!state.raw || !state.draft_windows.length;
    $('.tof-app').dataset.revision=state.revision;
    $('.tof-app').dataset.frame=state.frame;
    $('.tof-app').dataset.roi=JSON.stringify(state.roi);
    $('.tof-app').dataset.depthWindow=JSON.stringify(state.depth_window || null);
    $('.tof-app').dataset.peak=state.index;
    $('.tof-app').dataset.comparisons=JSON.stringify(state.comparisons.map(c=>c.id));
  }

  function bindPlot(key,gd) {
    if(key==='spectrum' || key==='profile') {
      const isDepth=key==='profile';
      let gesture=null;
      function position(e) {
        const rect=gd.getBoundingClientRect(), layout=gd._fullLayout;
        if(!layout) return null;
        const x=e.clientX-rect.left, y=e.clientY-rect.top, xa=layout.xaxis, ya=layout.yaxis;
        let value=xa.p2d(Math.max(0,Math.min(xa._length,x-xa._offset)));
        if(isDepth) {
          if(state.profile_axis==='depth') {
            const anchors=state.depth_calibration.anchors;
            value=Math.max(frameToProfile(Math.max(state.frames[0],anchors[0].frame),state),Math.min(frameToProfile(Math.min(state.frames[1],anchors.at(-1).frame),state),value));
          }
          value=Math.max(state.frames[0],Math.min(state.frames[1],Math.round(profileToFrame(value,state))));
        }
        return {pixel:x-xa._offset, mass:value,
          inside:x>=xa._offset && x<=xa._offset+xa._length && y>=ya._offset && y<=ya._offset+ya._length};
      }
      function band(low,high) {
        let shapes;
        if(isDepth) shapes=[gd.layout.shapes[0]];
        else {
          const id=gesture?.intervalId ?? intervalEditor.selectedId();
          shapes=(figures.spectrum.layout.shapes || []).filter(s=>s.name!==`draft:${id}`);
        }
        if(low!==null) {
          const shape={type:'rect',xref:'x',yref:'paper',x0:isDepth?frameToProfile(low,state):low,x1:isDepth?frameToProfile(high,state):high,
            y0:0,y1:1,editable:false,line:{color:'#d18c24',width:2},fillcolor:'rgba(209,140,36,.18)'};
          if(isDepth) shapes.push(shape);
          else {shape.name=`draft:${gesture?.intervalId ?? intervalEditor.selectedId()}`;shapes.unshift(shape);}
        }
        Plotly.relayout(gd,{shapes});
      }
      function preview(e) {
        if(!gesture) return;
        const pos=position(e);if(!pos) return;
        const {start,original,mode}=gesture;
        let limits;
        if(mode==='low') limits=[pos.mass,original[1]];
        else if(mode==='high') limits=[original[0],pos.mass];
        else if(mode==='move') limits=original.map(v=>v+pos.mass-start.mass);
        else limits=[start.mass,pos.mass];
        limits.sort((a,b)=>a-b);
        if(isDepth) limits=limits.map(v=>Math.max(state.frames[0],Math.min(state.frames[1],Math.round(v))));
        gesture.limits=limits;
        gesture.distance=Math.max(gesture.distance,Math.abs(e.clientX-gesture.clientX));
        band(...limits);
        if(isDepth) {
          input('first').value=limits[0];input('last').value=limits[1];
          field('depth-note').textContent=`Depth window ${limits[0]}–${limits[1]} · release to select`;
        } else {
          input('low').value=limits[0];input('high').value=limits[1];
          field('window-note').textContent=`${limits[0].toFixed(4)}–${limits[1].toFixed(4)} Th · release to set draft`;
        }
      }
      gd.addEventListener('pointerdown',(e)=>{
        if(e.button!==0 || e.target.closest('.modebar') || gd.layout.dragmode) return;
        const start=position(e);if(!start?.inside) return;
        const original=[...(isDepth?(state.depth_window || [state.frame,state.frame]):(selectedDraft() || [start.mass,start.mass]))], xa=gd._fullLayout.xaxis;
        const lowDistance=Math.abs(start.pixel-xa.d2p(isDepth?frameToProfile(original[0],state):original[0]));
        const highDistance=Math.abs(start.pixel-xa.d2p(isDepth?frameToProfile(original[1],state):original[1]));
        let mode='new';
        if(original[0]!==original[1] && Math.min(lowDistance,highDistance)<=7) mode=lowDistance<highDistance?'low':'high';
        else if(e.shiftKey && start.mass>=original[0] && start.mass<=original[1]) mode='move';
        gesture={start,original,mode,clientX:e.clientX,distance:0,limits:original,intervalId:isDepth?null:intervalEditor.selectedId()};
        e.preventDefault();e.stopImmediatePropagation();gd.setPointerCapture(e.pointerId);
      },true);
      gd.addEventListener('pointermove',(e)=>{
        if(gesture) {e.preventDefault();e.stopImmediatePropagation();preview(e);}
        else if(!gd.layout.dragmode) {
          const pos=position(e),xa=gd._fullLayout?.xaxis;
          const limits=isDepth?(state.depth_window || []):(selectedDraft() || []);
          const near=pos?.inside && limits.some(v=>Math.abs(pos.pixel-xa.d2p(v))<=7);
          gd.style.cursor=near?'ew-resize':'crosshair';
        }
      },true);
      gd.addEventListener('pointerup',(e)=>{
        if(!gesture) return;
        e.preventDefault();e.stopImmediatePropagation();
        const distance=Math.max(gesture.distance,Math.abs(e.clientX-gesture.clientX));
        if(distance>=3) preview(e);
        const finished=gesture;gesture=null;
        if(distance>=3 && finished.limits[1]>finished.limits[0]) {
          if(isDepth) send('depth_window',{bounds:finished.limits});
          else send(finished.intervalId===null?'interval_add':'interval_update',{id:finished.intervalId,bounds:finished.limits});
        }
        else if(isDepth) {
          band(...(state.depth_window || [null,null]));
          const pos=position(e);if(pos) send('frame',{frame:pos.mass});
        } else {band(...(state.draft || [null,null]));syncState(state);status('Drag horizontally to select a mass interval.');}
      },true);
      gd.addEventListener('pointercancel',()=>{if(gesture){gesture=null;band(...(isDepth?(state.depth_window || [null,null]):(state.draft || [null,null])));syncState(state);status('Ready');}},true);
    }
    if (key==='xz' || key==='yz' || key==='front') {
      let scrubbing=false;
      function coordinate(e) {
        const rect=gd.getBoundingClientRect(), layout=gd._fullLayout;
        if (!layout) return null;
        const x=e.clientX-rect.left, y=e.clientY-rect.top;
        const xa=layout.xaxis, ya=layout.yaxis;
        if (x<xa._offset || x>xa._offset+xa._length || y<ya._offset || y>ya._offset+ya._length) return null;
        const value = key==='profile'?xa.p2d(x-xa._offset):ya.p2d(y-ya._offset);
        return Math.max(state.frames[0],Math.min(state.frames[1],Math.round(value)));
      }
      let candidate=null;
      function preview(e) {
        const value=coordinate(e); if(value===null) return;
        candidate=value; input('frame').value=value;
        if (key==='profile') Plotly.relayout(gd,{'shapes[0].x0':value,'shapes[0].x1':value});
      }
      gd.addEventListener('pointerdown',(e)=>{
        if (e.button!==0 || e.target.closest('.modebar') || coordinate(e)===null) return;
        // Cross-sections keep their native zoom/pan behavior; clicks select Z.
        scrubbing=true; candidate=null; gd.setPointerCapture(e.pointerId); preview(e);
      },true);
      gd.addEventListener('pointermove',(e)=>{if(scrubbing && key==='profile') preview(e);},true);
      gd.addEventListener('pointerup',(e)=>{
        if(!scrubbing) return; scrubbing=false; preview(e);
        if(candidate!==null) send('frame',{frame:candidate});
      },true);
    }
    if (key==='ion') {
      gd.on('plotly_relayout',(change)=>{
        if(updating.has(key) || !Object.keys(change).some(k=>k.startsWith('shapes'))) return;
        const shapes=gd.layout.shapes || [];
        if(!shapes.length) {if(key==='ion') send('reset_roi');return;}
        const shape=shapes.at(-1);
        send('roi',{bounds:[shape.x0,shape.x1,shape.y0,shape.y1]});
      });
    }
  }
  function visibleKeys(){return focusedDisplay?[focusedDisplay.key]:tabs[active];}
  async function drawVisible() {
    if(state.loaded===false)return;
    for(const key of visibleKeys()) {
      const gd=plot(key);
      if(gd.closest('[hidden]')) continue;
      if(dirty.has(key) || !mounted.has(key)) {
        updating.add(key);
        const config={responsive:true,displaylogo:false,scrollZoom:key==='volume',
          modeBarButtonsToAdd:key==='ion'?['drawrect','eraseshape']:[],
          modeBarButtonsToRemove:(key==='spectrum'||key==='profile')?['select2d','lasso2d']:[]};
        await Plotly.react(gd,figures[key].data,figures[key].layout,config);
        if(!mounted.has(key)) {bindPlot(key,gd);mounted.add(key);}
        dirty.delete(key); updating.delete(key);
      }
      await Plotly.Plots.resize(gd);
    }
  }
  function redraw() {rendering=rendering.then(()=>disposed?null:drawVisible()).catch(e=>status(e.message,true));return rendering;}
  async function receive(message) {
    if(disposed) return;
    if(message.files){fileBrowser.update(message.files);return;}
    if(message.progress) {status(`Reconstructing frame ${message.progress.done} / ${message.progress.total}…`);return;}
    if(message.state) syncState(message.state,message.error);
    if(pendingOpen && message.state){pendingOpen=false;fileBrowser.opened(message.error);}
    for(const [key,figure] of Object.entries(message.figures || {})) {figures[key]=figure;dirty.add(key);}
    for(const [key,patch] of Object.entries(message.relayout || {})) {
      for(const [path,value] of Object.entries(patch)) {
        const match=path.match(/^shapes\[(\d+)\]\.(.+)$/);
        if(match && figures[key].layout.shapes?.[Number(match[1])]) figures[key].layout.shapes[Number(match[1])][match[2]]=value;
      }
      if(mounted.has(key) && visibleKeys().includes(key) && !plot(key).closest('[hidden]')) await Plotly.relayout(plot(key),patch);
      else dirty.add(key);
    }
    if(message.download) {
      const blob=new Blob([message.download.text],{type:message.download.filename.endsWith('.csv')?'text/csv':'application/json'});
      const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=message.download.filename;a.click();
      setTimeout(()=>URL.revokeObjectURL(a.href),1000);
    }
    await redraw();
    status(message.error || 'Ready',!!message.error);
  }
  model.on('msg:custom',receive);
  function showTab(name) {
    if(focusedDisplay) restoreDisplay();
    active=name;
    (name==='spectrum'?$('[data-panel="spectrum"]'):$('.tof-spectrum-home')).append($('.tof-spectrum-view'));
    for(const b of el.querySelectorAll('[data-tab]')) b.setAttribute('aria-selected',String(b.dataset.tab===name));
    for(const panel of el.querySelectorAll('[data-panel]')) panel.hidden=panel.dataset.panel!==active;
    redraw();
  }
  for(const button of el.querySelectorAll('[data-tab]')) button.addEventListener('click',()=>showTab(button.dataset.tab));
  input('frame').addEventListener('change',()=>send('frame',{frame:number('frame')}));
  for(const name of ['low','high']) input(name).addEventListener('change',()=>send('interval_update',{id:intervalEditor.selectedId(),bounds:[number('low'),number('high')]}));
  for(const name of ['first','last']) input(name).addEventListener('change',()=>send('draft_frames',{frames:[number('first'),number('last')]}));
  for(const name of ['log','relative','percentile','opacity','stretch','quality']) input(name).addEventListener('change',()=>{
    send('display',{log:input('log').checked,relative:input('relative').checked,
      percentile:number('percentile'),opacity:number('opacity'),stretch:number('stretch'),quality:input('quality').value});
  });
  const actions={
    prev:()=>send('frame',{frame:state.frame-1}), next:()=>send('frame',{frame:state.frame+1}),
    stored:()=>send('peak',{index:state.index}),
    'reset-roi':()=>send('reset_roi'),
    'roi-exact':()=>send('roi_pixels',{roi:['x0','x1','y0','y1'].map(number)}),
    integrate:()=>send('integrate',draftPayload()),
    'interval-add':()=>send('interval_add'),
    'comparison-window':()=>send('comparison_add',draftPayload()),
    'comparison-clear':()=>send('comparison_clear'),
    'restore-display':()=>restoreDisplay(),
    'export-csv':()=>send('export',{format:'csv'}), 'export-json':()=>send('export',{format:'json'}),
    'volume-edit-mass':()=>showTab('spectrum'),
    'volume-edit-region':()=>showTab('slices'),
    'volume-edit-roi':()=>{setImageMode('sims');showTab('slices');},
    'open-dialog':()=>fileBrowser.show(),
    'calibrate-depth':()=>depthEditor.show(),
    'zoom-window':()=>Plotly.relayout(plot('spectrum'),{'xaxis.range':[number('low')-2,number('high')+2]}),
    'draw-window':()=>{Plotly.relayout(plot('spectrum'),{dragmode:false});status('Drag horizontally to select a mass interval.');},
    'clear-depth':()=>send('clear_depth_window'),
    'all-depths':()=>send('clear_depth_window'),
    'zoom-spectrum':()=>Plotly.relayout(plot('spectrum'),{'xaxis.autorange':true}),
  };
  for(const button of el.querySelectorAll('[data-action]')) button.addEventListener('click',()=>actions[button.dataset.action]());
  function maximizeDisplay(key) {
    if(focusedDisplay) restoreDisplay();
    const frame=plot(key).closest('.tof-display'),placeholder=document.createComment(`display-${key}`);
    frame.before(placeholder);
    focusedDisplay={key,placeholder,frame};
    field('focus-title').textContent=displayNames[key];
    $('.tof-focus-body').append(frame);$('.tof-focus-pane').hidden=false;
    for(const background of el.querySelectorAll('.tof-sidebar,.tof-toolbar,[data-panel]')) background.inert=true;
    $('.tof-app').classList.add('tof-focused');
    $('[data-action="restore-display"]').focus();
    redraw();
  }
  function restoreDisplay() {
    if(!focusedDisplay) return;
    const {frame,placeholder}=focusedDisplay;
    for(const background of el.querySelectorAll('.tof-sidebar,.tof-toolbar,[data-panel]')) background.inert=false;
    placeholder.replaceWith(frame);focusedDisplay=null;
    $('.tof-focus-pane').hidden=true;$('.tof-app').classList.remove('tof-focused');
    frame.querySelector('.tof-maximize').focus();redraw();
  }
  function onEscape(e){if(e.key==='Escape' && focusedDisplay){e.preventDefault();restoreDisplay();}}
  document.addEventListener('keydown',onEscape);
  function setImageMode(mode) {
    imageMode=mode;
    for(const button of el.querySelectorAll('[data-image-mode]')) button.setAttribute('aria-pressed',String(button.dataset.imageMode===imageMode));
    for(const content of el.querySelectorAll('[data-image-content]')) content.hidden=content.dataset.imageContent!==imageMode;
    field('image-note').textContent=imageMode==='sims'?'Draw on the top map to select a spatial ROI. Front projection sums Y within that ROI.':'SE images are paired by index and shown in native pixels. Spatial registration and timing alignment are unverified; depth windows show an SE mean.';
    redraw();
  }
  for(const button of el.querySelectorAll('[data-image-mode]')) button.addEventListener('click',()=>setImageMode(button.dataset.imageMode));
  const observer=new ResizeObserver(()=>{if(mounted.size) redraw();});
  observer.observe($('.tof-main'));
  $('.tof-volume-details').addEventListener('toggle',()=>{if(mounted.size) redraw();});
  syncState(state);
  await redraw();status(state.startup_error || 'Ready',!!state.startup_error);
  return ()=>{disposed=true;observer.disconnect();document.removeEventListener('pointerdown',closePickers);document.removeEventListener('keydown',onEscape);intervalEditor.dispose();fileBrowser.dispose();depthEditor.dispose();model.off('msg:custom',receive);for(const key of mounted) Plotly.purge(plot(key));el.replaceChildren();};
}

export default {render};
