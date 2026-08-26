/*
 RAG 智能问答浮窗 SDK — 自包含单文件
 嵌入方式（客户页面加一行）：
   <script src="https://你的域名/widget/rag-widget.js"
           data-rag-api="https://你的域名"
           data-rag-lang="zh"
           data-rag-title="智能问答"></script>
 data-rag-api    : RAG 后端地址（默认同域）
 data-rag-lang   : zh / en
 data-rag-title  : 浮窗标题
*/
(function(){
"use strict";
var script=document.currentScript;
var cfg={
  api:script&&script.getAttribute("data-rag-api")||location.origin,
  lang:script&&script.getAttribute("data-rag-lang")||"zh",
  title:script&&script.getAttribute("data-rag-title")||"智能问答"
};
var i18n={
  zh:{ph:"输入问题…",send:"发送",think:"思考中…"},
  en:{ph:"Ask a question…",send:"Send",think:"Thinking…"}
};
var L=i18n[cfg.lang]||i18n.zh;

var root=document.createElement("div");
root.id="rag-widget-root";
root.innerHTML='<style>'+
'#rag-widget-root{position:fixed;bottom:24px;right:24px;z-index:99999;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans SC",sans-serif;--rp:#2563eb;--rm:#6b7280}'+
'#rag-toggle{width:56px;height:56px;border-radius:50%;background:var(--rp);border:none;color:#fff;cursor:pointer;box-shadow:0 6px 20px rgba(37,99,235,.35);display:flex;align-items:center;justify-content:center;transition:transform .2s}'+
'#rag-toggle:hover{transform:scale(1.05)}#rag-toggle svg{width:26px;height:26px}'+
'#rag-window{position:fixed;bottom:96px;right:24px;width:380px;max-height:560px;background:#fff;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,.18);display:none;flex-direction:column;overflow:hidden;border:1px solid #e5e7eb}'+
'#rag-window.open{display:flex}'+
'#rag-head{padding:16px 18px;background:var(--rp);color:#fff;display:flex;justify-content:space-between;align-items:center}'+
'#rag-head h3{margin:0;font-size:15px}#rag-head button{background:none;border:none;color:#fff;cursor:pointer;font-size:20px;line-height:1}'+
'#rag-messages{flex:1;overflow-y:auto;padding:14px 16px;display:flex;flex-direction:column;gap:10px;max-height:380px}'+
'.rag-msg{max-width:88%;padding:10px 13px;border-radius:12px;font-size:14px;line-height:1.55;word-break:break-word}'+
'.rag-user{align-self:flex-end;background:var(--rp);color:#fff;border-bottom-right-radius:4px}'+
'.rag-bot{align-self:flex-start;background:#f3f4f6;color:#1f2937;border-bottom-left-radius:4px}'+
'.rag-src{font-size:11px;color:var(--rm);margin-top:6px;display:block}'+
'.rag-loader{align-self:flex-start;padding:8px 14px;color:var(--rm);font-size:13px}'+
'#rag-input-row{display:flex;gap:8px;padding:12px 14px;border-top:1px solid #e5e7eb}'+
'#rag-input{flex:1;border:1px solid #d1d5db;border-radius:20px;padding:10px 14px;font-size:14px;outline:none}'+
'#rag-input:focus{border-color:var(--rp)}'+
'#rag-send{background:var(--rp);color:#fff;border:none;border-radius:20px;padding:0 16px;cursor:pointer;font-size:14px}'+
'#rag-send:disabled{opacity:.5;cursor:not-allowed}'+
'@media(max-width:480px){#rag-window{right:8px;left:8px;width:auto;bottom:80px}}'+
'</style>'+
'<button id="rag-toggle" aria-label="open chat"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z"/></svg></button>'+
'<div id="rag-window"><div id="rag-head"><h3>'+esc(cfg.title)+'</h3><button id="rag-close">&times;</button></div>'+
'<div id="rag-messages"></div>'+
'<div id="rag-input-row"><input id="rag-input" placeholder="'+esc(L.ph)+'" autocomplete="off"><button id="rag-send">'+esc(L.send)+'</button></div></div>';
document.body.appendChild(root);

var toggle=root.querySelector("#rag-toggle");
var win=root.querySelector("#rag-window");
var msgs=root.querySelector("#rag-messages");
var input=root.querySelector("#rag-input");
var send=root.querySelector("#rag-send");
toggle.onclick=function(){win.classList.toggle("open");if(win.classList.contains("open"))input.focus();};
root.querySelector("#rag-close").onclick=function(){win.classList.remove("open");};

function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/\n/g,"<br>");}
function addMsg(html,cls){var d=document.createElement("div");d.className="rag-msg "+cls;d.innerHTML=html;msgs.appendChild(d);msgs.scrollTop=msgs.scrollHeight;}
function fmtSrc(srcs){var out=[];for(var i=0;i<Math.min(srcs.length,3);i++){out.push("【"+(srcs[i].doc||"")+"】");}return out.join(" ");}

async function ask(q){
  if(!q.trim())return;
  addMsg(esc(q),"rag-user");
  input.value="";send.disabled=true;
  var loader=document.createElement("div");loader.className="rag-loader";loader.textContent=L.think;msgs.appendChild(loader);
  try{
    var r=await fetch(cfg.api+"/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:q})});
    var j=await r.json();
    msgs.removeChild(loader);
    var ans=j.answer||"（未得到回答）";
    var sh=j.sources&&j.sources.length?"<span class='rag-src'>来源："+fmtSrc(j.sources)+"</span>":"";
    addMsg(ans+sh,"rag-bot");
  }catch(e){msgs.removeChild(loader);addMsg("（请求失败，请检查网络）","rag-bot");}
  send.disabled=false;input.focus();
}
send.onclick=function(){ask(input.value);};
input.onkeydown=function(e){if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();ask(input.value);}};
})();
