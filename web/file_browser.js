// Local module: directory metadata only; acquisition arrays stay on the server.
export function mountFileBrowser(root,{requestPage,openFile}) {
  root.innerHTML=`<h3 id="files-title">Open acquisition</h3><nav aria-label="Data directories"></nav>
    <label>Filter files<input type="search" aria-label="Filter files"></label>
    <p class="tof-files-summary" aria-live="polite"></p><div class="tof-files-list" role="list" aria-label="Server files"></div>
    <p role="alert"></p><div class="tof-files-pages"><button type="button" data-page="prev">Previous page</button><button type="button" data-page="next">Next page</button></div>
    <div class="tof-files-actions"><button type="button" data-close>Cancel</button><button type="button" data-open class="tof-primary" disabled>Open dataset</button></div>`;
  root.setAttribute('aria-labelledby','files-title');
  const $=s=>root.querySelector(s),list=$('[role=list]'),error=$('[role=alert]'),summary=$('.tof-files-summary'),search=$('input');
  let requestId=0,current='',offset=0,next=null,selected=null,opening=false,disposed=false;
  function load(path=current,start=0) {
    current=path;offset=start;selected=null;opening=false;list.replaceChildren();error.textContent='';summary.textContent='Loading…';
    $('[data-open]').disabled=true;$('[data-page=prev]').disabled=true;$('[data-page=next]').disabled=true;
    requestPage({path,query:search.value,offset:start,request_id:++requestId});
  }
  function breadcrumbs() {
    const nav=$('nav');nav.replaceChildren();
    const parts=current.split('/').filter(Boolean);
    for(let i=0;i<=parts.length;i++) {
      const b=document.createElement('button');b.type='button';b.textContent=i?parts[i-1]:'Data';
      b.addEventListener('click',()=>{search.value='';load(parts.slice(0,i).join('/'));});nav.append(b);
    }
  }
  function update(page) {
    if(disposed || page.request_id!==requestId)return;
    if(page.error){error.textContent=page.error;summary.textContent='Unable to list this directory';breadcrumbs();return;}
    current=page.path;next=page.next_offset;breadcrumbs();list.replaceChildren();
    summary.textContent=page.total?`${offset+1}–${offset+page.entries.length} of ${page.total}`:'No matching files';
    $('[data-page=prev]').disabled=offset===0;$('[data-page=next]').disabled=next===null;
    for(const entry of page.entries) {
      const b=document.createElement('button');b.type='button';b.dataset.filePath=entry.path;b.setAttribute('role','listitem');
      const name=document.createElement('strong');name.textContent=(entry.kind==='directory'?'▸ ':'')+entry.name;
      const detail=document.createElement('small');detail.textContent=entry.kind==='directory'?'Folder':`${(entry.size/2**20).toFixed(1)} MiB`;
      b.append(name,detail);
      b.addEventListener('click',()=>{
        if(opening)return;
        for(const row of list.children)row.setAttribute('aria-current','false');b.setAttribute('aria-current','true');
        selected=entry;$('[data-open]').disabled=false;$('[data-open]').textContent=entry.kind==='directory'?'Open folder':'Open dataset';
      });
      b.addEventListener('dblclick',()=>{selected=entry;open();});list.append(b);
    }
  }
  function open() {
    if(!selected || opening)return;
    if(selected.kind==='directory'){search.value='';load(selected.path);return;}
    opening=true;error.textContent='';$('[data-open]').disabled=true;summary.textContent='Opening…';openFile(selected.path);
  }
  search.addEventListener('input',()=>load());
  // Search inputs consume Escape to clear their value before native dialogs
  // receive it. Handle it here so keyboard dismissal is consistent.
  function dismiss(e){if(e.key==='Escape'){e.preventDefault();e.stopPropagation();root.close();}}
  root.addEventListener('keydown',dismiss,true);
  $('[data-page=prev]').addEventListener('click',()=>load(current,Math.max(0,offset-100)));
  $('[data-page=next]').addEventListener('click',()=>{if(next!==null)load(current,next);});
  $('[data-open]').addEventListener('click',open);$('[data-close]').addEventListener('click',()=>root.close());
  return {show(){root.showModal();load();search.focus();},update,
    opened(errorMessage){opening=false;if(errorMessage){error.textContent=errorMessage;summary.textContent='Choose another file';$('[data-open]').disabled=!selected;}else root.close();},
    dispose(){disposed=true;root.removeEventListener('keydown',dismiss,true);root.replaceChildren();}};
}
