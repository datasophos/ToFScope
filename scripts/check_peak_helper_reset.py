"""File switches invalidate selected candidates and in-flight search replies."""
from pathlib import Path
from playwright.sync_api import sync_playwright

source=(Path(__file__).resolve().parents[1]/'web/peak_helper.js').read_text()
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page()
    try:
        result=page.evaluate('''async source=>{
          const url=URL.createObjectURL(new Blob([source],{type:'text/javascript'}));
          const {mountPeakHelper}=await import(url);URL.revokeObjectURL(url);
          const dialog=document.createElement('dialog'),table=document.createElement('div');document.body.append(dialog,table);
          const requests=[];const helper=mountPeakHelper(dialog,table,{send(event,payload){requests.push(payload)},apply(){},compare(){}});
          const state={loaded:true,path:'a.h5',raw:true,recipe:{id:'a',label:'ion'},comparisons:[],abundance_rows:[],abundance_context:null};
          helper.sync(state);
          const candidate={id:'Al-27:+1',predicted_mz:26.981,error_Th:.001,error_ppm:37,isotope:{abundance_low:1,abundance_high:1,source_id:'fixture'}};
          dialog.querySelector('[data-find]').click();const requestId=requests.at(-1).request_id;
          helper.candidates({request_id:requestId,rows:[candidate]});dialog.querySelector('tbody button').click();
          if(dialog.querySelector('[data-annotate]').disabled)throw Error('fixture selection did not enable annotation');
          helper.sync({...state,path:'b.h5',recipe:{id:'b',label:'other'}});
          const disabled=['annotate','apply','compare'].every(key=>dialog.querySelector(`[data-${key}]`).disabled);
          helper.candidates({request_id:requestId,rows:[candidate]});
          return {disabled,oldRows:dialog.querySelectorAll('[data-candidate]').length,lower:dialog.querySelector('[aria-label="Candidate window lower"]').value};
        }''',source)
        assert result==dict(disabled=True,oldRows=0,lower=''),result
        print('PASS: file switches disable stale actions, clear bounds and ignore old candidate replies',flush=True)
    finally:browser.close()
