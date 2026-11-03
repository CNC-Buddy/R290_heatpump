import {esc} from './model.js?v=1.1.1';
import {tr, translateTree} from './i18n.js?v=1.1.1';

const normalize=value=>String(value??'').trim().toLocaleLowerCase('de-DE').replace(/[äöüß]/g,c=>({ä:'ae',ö:'oe',ü:'ue',ß:'ss'}[c]));

// Searchable, local-only entity combobox. An unselected query is never saved as
// an entity ID. Native paste, keyboard selection and form validity are retained.
class R290EntityPicker extends HTMLElement {
  constructor(){
    super();this.attachShadow({mode:'open'});this._items=[];this._value='';this._open=false;this._query='';this._active=-1;
    this.shadowRoot.innerHTML=`<style>
      :host{display:block;position:relative;min-width:0;font:inherit;--picker-border:var(--line,#ddd5cb)}*{box-sizing:border-box}
      .control{position:relative;display:flex;align-items:center;border:1px solid var(--picker-border);border-radius:8px;background:var(--surface,#fffdfa)}
      .control:focus-within{outline:2px solid var(--accent,#bd4d2f);outline-offset:2px}
      input{font:inherit;font-weight:400;color:var(--ink,#20323f);background:transparent;border:0;outline:0;min-width:0;width:100%;height:41px;padding:10px 38px 10px 11px;text-overflow:ellipsis}
      input::placeholder{color:var(--muted,#65717b)}button{font:inherit;color:var(--muted,#65717b);border:0;background:transparent;cursor:pointer}
      .toggle{position:absolute;right:1px;top:1px;height:39px;width:34px;border-radius:7px;font-size:17px}.toggle:hover{background:var(--bg,#f6f3ee)}button:focus-visible{outline:2px solid var(--accent,#bd4d2f);outline-offset:1px}
      .selected-id{font-size:10px;font-weight:400;color:var(--muted,#65717b);margin-top:5px;overflow-wrap:anywhere;line-height:1.5}
      .popup{position:absolute;left:0;right:0;top:47px;z-index:30;background:var(--surface,#fffdfa);border:1px solid var(--picker-border);border-radius:9px;box-shadow:0 8px 25px #20323f22;overflow:hidden;font-weight:400}
      .popup.above{top:auto;bottom:calc(100% + 6px)}.results{overflow:auto;overscroll-behavior:contain;max-height:240px}
      .option{padding:10px 12px;cursor:pointer;display:flex;flex-direction:column;gap:4px;line-height:1.4;border-bottom:1px solid var(--picker-border)}.option:last-child{border:0}
      .option.active{background:var(--bg,#f6f3ee);box-shadow:inset 3px 0 var(--accent,#bd4d2f)}.option[aria-selected=true] .name:after{content:' ✓';color:var(--accent,#bd4d2f)}
      .name{font-size:12px;color:var(--ink,#20323f);overflow-wrap:anywhere}.entity-id,.hint{font-size:10px;color:var(--muted,#65717b);overflow-wrap:anywhere}.hint{padding:8px 12px;background:var(--bg,#f6f3ee);line-height:1.5}.empty{padding:14px 12px;font-size:12px;color:var(--muted,#65717b)}[hidden]{display:none!important}
      @media(pointer:coarse){input{font-size:16px;height:44px}.toggle{height:42px}.option{min-height:48px}}
    </style><div class="control"><input type="text" role="combobox" aria-autocomplete="list" aria-haspopup="listbox" aria-expanded="false" aria-controls="results" autocomplete="off" spellcheck="false"><button class="toggle" type="button" aria-label="Auswahl öffnen" tabindex="-1">⌄</button></div><div class="selected-id"></div><div class="popup" hidden><div id="results" class="results" role="listbox"></div><div class="hint" role="status" aria-live="polite"></div></div>`;
    this.input=this.shadowRoot.querySelector('input');this.popup=this.shadowRoot.querySelector('.popup');
    this.input.addEventListener('focus',()=>{this.open('');this.input.select();});
    this.input.addEventListener('input',()=>{this.input.setCustomValidity('');this.open(this.input.value);});
    this.input.addEventListener('keydown',event=>this.keydown(event));
    this.shadowRoot.querySelector('.toggle').addEventListener('pointerdown',event=>event.preventDefault());
    this.shadowRoot.querySelector('.toggle').addEventListener('click',()=>{if(this._open)this.close();else{this.input.focus();this.open('');}});
    this.shadowRoot.querySelector('.results').addEventListener('pointerdown',event=>event.preventDefault());
    this.shadowRoot.querySelector('.results').addEventListener('click',event=>{const option=event.target.closest('[data-index]');if(option)this.choose(this._matches[Number(option.dataset.index)]);});
    this.shadowRoot.addEventListener('focusout',event=>{if(!this.shadowRoot.contains(event.relatedTarget)){this.resolve(false);this.close();}});
  }
  configure(items,value,label,language='de'){
    this.language=language;
    this._items=items;this._label=label;this.input.setAttribute('aria-label',label);this.shadowRoot.querySelector('.toggle').setAttribute('aria-label',`${label}: Auswahl öffnen`);
    this.setValue(value||'');this.setLanguage(language);
  }
  setLanguage(language){this.language=language;translateTree(this.shadowRoot,language);}
  setValue(value){this._value=value;this._query='';this.input.value=value?(this._items.find(i=>i.id===value)?.name||value):'';this.input.placeholder='Namen oder Entity-ID suchen / einfügen';this.input.setCustomValidity('');this.shadowRoot.querySelector('.selected-id').textContent=value||'Automatische Zuordnung / nicht hinterlegt';translateTree(this.shadowRoot,this.language);}
  get value(){return this._value;}
  matchingItems(query){
    const terms=normalize(query).split(/\s+/).filter(Boolean);
    const all=[{id:'',name:'Automatische Zuordnung / nicht hinterlegt',unit:''},...this._items];
    const filtered=terms.length?all.filter(i=>terms.every(term=>normalize(`${i.id} ${i.name} ${i.unit||''}`).includes(term))):all;
    const exact=normalize(query);filtered.sort((a,b)=>(normalize(b.id)===exact&&b.id?1:0)-(normalize(a.id)===exact&&a.id?1:0));
    this._total=filtered.length;return filtered.slice(0,60);
  }
  open(query=this._query){
    this._query=query;this._matches=this.matchingItems(query);this._active=-1;this._open=true;this.input.setAttribute('aria-expanded','true');this.popup.hidden=false;
    const box=this.getBoundingClientRect(),bottom=window.innerHeight-box.bottom,above=box.top;
    const flip=bottom<200&&above>bottom;this.popup.classList.toggle('above',flip);
    this.shadowRoot.querySelector('.results').style.maxHeight=`${Math.max(100,Math.min(260,(flip?above:bottom)-55))}px`;
    this.renderOptions();
  }
  renderOptions(){
    const list=this.shadowRoot.querySelector('.results');
    list.innerHTML=this._matches.length?this._matches.map((item,i)=>`<div class="option ${i===this._active?'active':''}" role="option" id="option-${i}" data-index="${i}" aria-selected="${item.id===this._value}"><span class="name">${esc(item.name)}</span>${item.id?`<span class="entity-id">${esc(item.id)}${item.unit?` · ${esc(item.unit)}`:''}</span>`:''}</div>`).join(''):'<div class="empty">Keine passende Entität gefunden.</div>';
    this.shadowRoot.querySelector('.hint').textContent=this._total>60?`${this._total} Treffer · erste 60 angezeigt. Suche weiter eingrenzen.`:`${this._total} Treffer · ↑ ↓ auswählen · Enter übernehmen · Esc schließen`;
    if(this._active>=0)this.input.setAttribute('aria-activedescendant',`option-${this._active}`);else this.input.removeAttribute('aria-activedescendant');
    translateTree(this.shadowRoot,this.language);
  }
  choose(item){if(!item)return;this.setValue(item.id);this.close();this.input.focus();this.dispatchEvent(new Event('change',{bubbles:true,composed:true}));}
  close(){this._open=false;this.popup.hidden=true;this.input.setAttribute('aria-expanded','false');this.input.removeAttribute('aria-activedescendant');}
  keydown(event){
    if(event.key==='Escape'){if(this._open){event.preventDefault();event.stopPropagation();this.setValue(this._value);this.close();}return;}
    if(event.key==='ArrowDown'||event.key==='ArrowUp'){
      event.preventDefault();if(!this._open)this.open(this.input.value===this._items.find(i=>i.id===this._value)?.name?'':this.input.value);
      if(!this._matches.length)return;
      this._active=this._active<0?(event.key==='ArrowDown'?0:this._matches.length-1):(this._active+(event.key==='ArrowDown'?1:-1)+this._matches.length)%this._matches.length;
      this.renderOptions();this.shadowRoot.getElementById(`option-${this._active}`)?.scrollIntoView({block:'nearest'});return;
    }
    if(event.key==='Enter'&&this._open){event.preventDefault();if(this._active>=0)this.choose(this._matches[this._active]);else if(this._matches.length===1)this.choose(this._matches[0]);else if(this.resolve(false))this.close();}
  }
  resolve(showError){
    const query=this.input.value.trim(), selected=this._items.find(i=>i.id===this._value);
    if(query===(selected?.name||this._value))return true;
    const id=normalize(query), exact=this._items.find(i=>normalize(i.id)===id);
    const names=this._items.filter(i=>normalize(i.name)===id);
    if(!query||exact||names.length===1){this.setValue(exact?.id||names[0]?.id||'');return true;}
    if(showError){this.input.setCustomValidity(tr('Bitte einen Treffer auswählen oder eine passende Entity-ID einfügen. Leer bedeutet automatische Zuordnung.',this.language));this.input.reportValidity();this.open(query);}
    return false;
  }
  reportValidity(){return this.resolve(true);}
}
if(!customElements.get('r290-entity-picker'))customElements.define('r290-entity-picker',R290EntityPicker);
