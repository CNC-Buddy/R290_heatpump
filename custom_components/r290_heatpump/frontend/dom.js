// Update mounted nodes so HA's scroll containers and CSS animations survive
// state reports. Keys retain identity when optional notices/rows are inserted.
const key = node => node.nodeType === 1 ? node.id || node.getAttribute('data-key') || node.getAttribute('data-detail-id') || node.getAttribute('data-view') || '' : '';
const compatible = (a,b) => a.nodeType === b.nodeType && a.nodeName === b.nodeName && key(a) === key(b);
export function patchElement(node, fresh) {
  if(node.nodeType !== 1){if(node.nodeValue !== fresh.nodeValue)node.nodeValue=fresh.nodeValue;return;}
  for(const attr of [...node.attributes])if(!(node.tagName==='DETAILS'&&attr.name==='open')&&!fresh.hasAttribute(attr.name))node.removeAttribute(attr.name);
  for(const attr of fresh.attributes)if(node.getAttribute(attr.name)!==attr.value)node.setAttribute(attr.name,attr.value);
  if(node instanceof HTMLTextAreaElement && node===node.getRootNode().activeElement)return;
  if(!fresh.hasAttribute('data-preserve-children'))reconcile(node,fresh);
  if(node instanceof HTMLTextAreaElement)node.value=fresh.value;
  if(node instanceof HTMLInputElement){node.value=fresh.value;node.checked=fresh.checked;}
  if(node instanceof HTMLSelectElement)node.value=fresh.value;
}
function reconcile(target, source){
  let cursor=target.firstChild;
  for(const fresh of [...source.childNodes]){
    let match=cursor&&compatible(cursor,fresh)?cursor:null;
    if(!match&&key(fresh))match=[...target.childNodes].find(n=>compatible(n,fresh));
    if(match){if(match!==cursor)target.insertBefore(match,cursor);patchElement(match,fresh);cursor=match.nextSibling;}
    else {target.insertBefore(fresh.cloneNode(true),cursor);}
  }
  while(cursor){const next=cursor.nextSibling;cursor.remove();cursor=next;}
}
export function patchHTML(target,html){const template=document.createElement('template');template.innerHTML=html;reconcile(target,template.content);}
export function preserveScroll(host){
  const elements=[...host.shadowRoot.querySelectorAll('*')];
  for(let node=host;node;node=node.parentElement||node.getRootNode()?.host)elements.push(node);
  if(document.scrollingElement)elements.push(document.scrollingElement);
  const saved=[...new Set(elements)].filter(n=>n.scrollTop||n.scrollLeft).map(n=>[n,n.scrollTop,n.scrollLeft]);
  return ()=>{for(const [node,top,left] of saved)if(node.isConnected){node.scrollTop=top;node.scrollLeft=left;}};
}
