(function(){"use strict";var ne,y,Xe,F,Qe,Ge,Ze,Ee,re,G,et,Se,Ce,Te,se={},ie=[],Wt=/acit|ex(?:s|g|n|p|$)|rph|grid|ows|mnc|ntw|ine[ch]|zoo|^ord|itera/i,oe=Array.isArray;function M(n,e){for(var t in e)n[t]=e[t];return n}function Ae(n){n&&n.parentNode&&n.parentNode.removeChild(n)}function tt(n,e,t){var r,s,i,o={};for(i in e)i=="key"?r=e[i]:i=="ref"?s=e[i]:o[i]=e[i];if(arguments.length>2&&(o.children=arguments.length>3?ne.call(arguments,2):t),typeof n=="function"&&n.defaultProps!=null)for(i in n.defaultProps)o[i]===void 0&&(o[i]=n.defaultProps[i]);return ae(n,o,r,s,null)}function ae(n,e,t,r,s){var i={type:n,props:e,key:t,ref:r,__k:null,__:null,__b:0,__e:null,__c:null,constructor:void 0,__v:s??++Xe,__i:-1,__u:0};return s==null&&y.vnode!=null&&y.vnode(i),i}function j(n){return n.children}function ce(n,e){this.props=n,this.context=e}function J(n,e){if(e==null)return n.__?J(n.__,n.__i+1):null;for(var t;e<n.__k.length;e++)if((t=n.__k[e])!=null&&t.__e!=null)return t.__e;return typeof n.type=="function"?J(n):null}function Yt(n){if(n.__P&&n.__d){var e=n.__v,t=e.__e,r=[],s=[],i=M({},e);i.__v=e.__v+1,y.vnode&&y.vnode(i),Oe(n.__P,i,e,n.__n,n.__P.namespaceURI,32&e.__u?[t]:null,r,t??J(e),!!(32&e.__u),s),i.__v=e.__v,i.__.__k[i.__i]=i,lt(r,i,s),e.__e=e.__=null,i.__e!=t&&nt(i)}}function nt(n){if((n=n.__)!=null&&n.__c!=null)return n.__e=n.__c.base=null,n.__k.some(function(e){if(e!=null&&e.__e!=null)return n.__e=n.__c.base=e.__e}),nt(n)}function rt(n){(!n.__d&&(n.__d=!0)&&F.push(n)&&!le.__r++||Qe!=y.debounceRendering)&&((Qe=y.debounceRendering)||Ge)(le)}function le(){try{for(var n,e=1;F.length;)F.length>e&&F.sort(Ze),n=F.shift(),e=F.length,Yt(n)}finally{F.length=le.__r=0}}function st(n,e,t,r,s,i,o,c,h,l,d){var _,a,p,v,C,E,w,b=r&&r.__k||ie,O=e.length;for(h=jt(t,e,b,h,O),_=0;_<O;_++)(p=t.__k[_])!=null&&(a=p.__i!=-1&&b[p.__i]||se,p.__i=_,E=Oe(n,p,a,s,i,o,c,h,l,d),v=p.__e,p.ref&&a.ref!=p.ref&&(a.ref&&Be(a.ref,null,p),d.push(p.ref,p.__c||v,p)),C==null&&v!=null&&(C=v),(w=!!(4&p.__u))||a.__k===p.__k?(h=it(p,h,n,w),w&&a.__e&&(a.__e=null)):typeof p.type=="function"&&E!==void 0?h=E:v&&(h=v.nextSibling),p.__u&=-7);return t.__e=C,h}function jt(n,e,t,r,s){var i,o,c,h,l,d=t.length,_=d,a=0;for(n.__k=new Array(s),i=0;i<s;i++)(o=e[i])!=null&&typeof o!="boolean"&&typeof o!="function"?(typeof o=="string"||typeof o=="number"||typeof o=="bigint"||o.constructor==String?o=n.__k[i]=ae(null,o,null,null,null):oe(o)?o=n.__k[i]=ae(j,{children:o},null,null,null):o.constructor===void 0&&o.__b>0?o=n.__k[i]=ae(o.type,o.props,o.key,o.ref?o.ref:null,o.__v):n.__k[i]=o,h=i+a,o.__=n,o.__b=n.__b+1,c=null,(l=o.__i=Kt(o,t,h,_))!=-1&&(_--,(c=t[l])&&(c.__u|=2)),c==null||c.__v==null?(l==-1&&(s>d?a--:s<d&&a++),typeof o.type!="function"&&(o.__u|=4)):l!=h&&(l==h-1?a--:l==h+1?a++:(l>h?a--:a++,o.__u|=4))):n.__k[i]=null;if(_)for(i=0;i<d;i++)(c=t[i])!=null&&(2&c.__u)==0&&(c.__e==r&&(r=J(c)),ut(c,c));return r}function it(n,e,t,r){var s,i;if(typeof n.type=="function"){for(s=n.__k,i=0;s&&i<s.length;i++)s[i]&&(s[i].__=n,e=it(s[i],e,t,r));return e}n.__e!=e&&(r&&(e&&n.type&&!e.parentNode&&(e=J(n)),t.insertBefore(n.__e,e||null)),e=n.__e);do e=e&&e.nextSibling;while(e!=null&&e.nodeType==8);return e}function Kt(n,e,t,r){var s,i,o,c=n.key,h=n.type,l=e[t],d=l!=null&&(2&l.__u)==0;if(l===null&&c==null||d&&c==l.key&&h==l.type)return t;if(r>(d?1:0)){for(s=t-1,i=t+1;s>=0||i<e.length;)if((l=e[o=s>=0?s--:i++])!=null&&(2&l.__u)==0&&c==l.key&&h==l.type)return o}return-1}function ot(n,e,t){e[0]=="-"?n.setProperty(e,t??""):n[e]=t==null?"":typeof t!="number"||Wt.test(e)?t:t+"px"}function he(n,e,t,r,s){var i,o;e:if(e=="style")if(typeof t=="string")n.style.cssText=t;else{if(typeof r=="string"&&(n.style.cssText=r=""),r)for(e in r)t&&e in t||ot(n.style,e,"");if(t)for(e in t)r&&t[e]==r[e]||ot(n.style,e,t[e])}else if(e[0]=="o"&&e[1]=="n")i=e!=(e=e.replace(et,"$1")),o=e.toLowerCase(),e=o in n||e=="onFocusOut"||e=="onFocusIn"?o.slice(2):e.slice(2),n.l||(n.l={}),n.l[e+i]=t,t?r?t[G]=r[G]:(t[G]=Se,n.addEventListener(e,i?Te:Ce,i)):n.removeEventListener(e,i?Te:Ce,i);else{if(s=="http://www.w3.org/2000/svg")e=e.replace(/xlink(H|:h)/,"h").replace(/sName$/,"s");else if(e!="width"&&e!="height"&&e!="href"&&e!="list"&&e!="form"&&e!="tabIndex"&&e!="download"&&e!="rowSpan"&&e!="colSpan"&&e!="role"&&e!="popover"&&e in n)try{n[e]=t??"";break e}catch{}typeof t=="function"||(t==null||t===!1&&e[4]!="-"?n.removeAttribute(e):n.setAttribute(e,e=="popover"&&t==1?"":t))}}function at(n){return function(e){if(this.l){var t=this.l[e.type+n];if(e[re]==null)e[re]=Se++;else if(e[re]<t[G])return;return t(y.event?y.event(e):e)}}}function Oe(n,e,t,r,s,i,o,c,h,l){var d,_,a,p,v,C,E,w,b,O,N,k,B,V,q,W,R=e.type;if(e.constructor!==void 0)return null;128&t.__u&&(h=!!(32&t.__u),i=[c=e.__e=t.__e]),(d=y.__b)&&d(e);e:if(typeof R=="function"){_=o.length;try{if(b=e.props,O=R.prototype&&R.prototype.render,N=(d=R.contextType)&&r[d.__c],k=d?N?N.props.value:d.__:r,t.__c?w=(a=e.__c=t.__c).__=a.__E:(O?e.__c=a=new R(b,k):(e.__c=a=new ce(b,k),a.constructor=R,a.render=Xt),N&&N.sub(a),a.state||(a.state={}),a.__n=r,p=a.__d=!0,a.__h=[],a._sb=[]),O&&a.__s==null&&(a.__s=a.state),O&&R.getDerivedStateFromProps!=null&&(a.__s==a.state&&(a.__s=M({},a.__s)),M(a.__s,R.getDerivedStateFromProps(b,a.__s))),v=a.props,C=a.state,a.__v=e,p)O&&R.getDerivedStateFromProps==null&&a.componentWillMount!=null&&a.componentWillMount(),O&&a.componentDidMount!=null&&a.__h.push(a.componentDidMount);else{if(O&&R.getDerivedStateFromProps==null&&b!==v&&a.componentWillReceiveProps!=null&&a.componentWillReceiveProps(b,k),e.__v==t.__v||!a.__e&&a.shouldComponentUpdate!=null&&a.shouldComponentUpdate(b,a.__s,k)===!1){e.__v!=t.__v&&(a.props=b,a.state=a.__s,a.__d=!1),e.__e=t.__e,e.__k=t.__k,e.__k.some(function(U){U&&(U.__=e)}),ie.push.apply(a.__h,a._sb),a._sb=[],a.__h.length&&o.push(a);break e}a.componentWillUpdate!=null&&a.componentWillUpdate(b,a.__s,k),O&&a.componentDidUpdate!=null&&a.__h.push(function(){a.componentDidUpdate(v,C,E)})}if(a.context=k,a.props=b,a.__P=n,a.__e=!1,B=y.__r,V=0,O)a.state=a.__s,a.__d=!1,B&&B(e),d=a.render(a.props,a.state,a.context),ie.push.apply(a.__h,a._sb),a._sb=[];else do a.__d=!1,B&&B(e),d=a.render(a.props,a.state,a.context),a.state=a.__s;while(a.__d&&++V<25);a.state=a.__s,a.getChildContext!=null&&(r=M(M({},r),a.getChildContext())),O&&!p&&a.getSnapshotBeforeUpdate!=null&&(E=a.getSnapshotBeforeUpdate(v,C)),q=d!=null&&d.type===j&&d.key==null?ht(d.props.children):d,c=st(n,oe(q)?q:[q],e,t,r,s,i,o,c,h,l),a.base=e.__e,e.__u&=-161,a.__h.length&&o.push(a),w&&(a.__E=a.__=null)}catch(U){if(o.length=_,e.__v=null,h||i!=null){if(U.then){for(e.__u|=h?160:128;c&&c.nodeType==8&&c.nextSibling;)c=c.nextSibling;i!=null&&(i[i.indexOf(c)]=null),e.__e=c}else if(i!=null)for(W=i.length;W--;)Ae(i[W])}else e.__e=t.__e;e.__k==null&&(e.__k=t.__k||[]),U.then||ct(e),y.__e(U,e,t)}}else i==null&&e.__v==t.__v?(e.__k=t.__k,e.__e=t.__e):c=e.__e=Jt(t.__e,e,t,r,s,i,o,h,l);return(d=y.diffed)&&d(e),128&e.__u?void 0:c}function ct(n){n&&(n.__c&&(n.__c.__e=!0),n.__k&&n.__k.some(ct))}function lt(n,e,t){for(var r=0;r<t.length;r++)Be(t[r],t[++r],t[++r]);y.__c&&y.__c(e,n),n.some(function(s){try{n=s.__h,s.__h=[],n.some(function(i){i.call(s)})}catch(i){y.__e(i,s.__v)}})}function ht(n){return typeof n!="object"||n==null||n.__b>0?n:oe(n)?n.map(ht):n.constructor!==void 0?null:M({},n)}function Jt(n,e,t,r,s,i,o,c,h){var l,d,_,a,p,v,C,E=t.props||se,w=e.props,b=e.type;if(b=="svg"?s="http://www.w3.org/2000/svg":b=="math"?s="http://www.w3.org/1998/Math/MathML":s||(s="http://www.w3.org/1999/xhtml"),i!=null){for(l=0;l<i.length;l++)if((p=i[l])&&"setAttribute"in p==!!b&&(b?p.localName==b:p.nodeType==3)){n=p,i[l]=null;break}}if(n==null){if(b==null)return document.createTextNode(w);n=document.createElementNS(s,b,w.is&&w),c&&(y.__m&&y.__m(e,i),c=!1),i=null}if(b==null)E===w||c&&n.data==w||(n.data=w);else{if(i=b=="textarea"&&w.defaultValue!=null?null:i&&ne.call(n.childNodes),!c&&i!=null)for(E={},l=0;l<n.attributes.length;l++)E[(p=n.attributes[l]).name]=p.value;for(l in E)p=E[l],l=="dangerouslySetInnerHTML"?_=p:l=="children"||l in w||l=="value"&&"defaultValue"in w||l=="checked"&&"defaultChecked"in w||he(n,l,null,p,s);for(l in w)p=w[l],l=="children"?a=p:l=="dangerouslySetInnerHTML"?d=p:l=="value"?v=p:l=="checked"?C=p:c&&typeof p!="function"||E[l]===p||he(n,l,p,E[l],s);if(d)c||_&&(d.__html==_.__html||d.__html==n.innerHTML)||(n.innerHTML=d.__html),e.__k=[];else if(_&&(n.innerHTML=""),st(e.type=="template"?n.content:n,oe(a)?a:[a],e,t,r,b=="foreignObject"?"http://www.w3.org/1999/xhtml":s,i,o,i?i[0]:t.__k&&J(t,0),c,h),i!=null)for(l=i.length;l--;)Ae(i[l]);c&&b!="textarea"||(l="value",b=="progress"&&v==null?n.removeAttribute("value"):v!=null&&(v!==n[l]||b=="progress"&&!v||b=="option"&&v!=E[l])&&he(n,l,v,E[l],s),l="checked",C!=null&&C!=n[l]&&he(n,l,C,E[l],s))}return n}function Be(n,e,t){try{if(typeof n=="function"){var r=typeof n.__u=="function";r&&n.__u(),r&&e==null||(n.__u=n(e))}else n.current=e}catch(s){y.__e(s,t)}}function ut(n,e,t){var r,s;if(y.unmount&&y.unmount(n),(r=n.ref)&&(r.current&&r.current!=n.__e||Be(r,null,e)),(r=n.__c)!=null){if(r.componentWillUnmount)try{r.componentWillUnmount()}catch(i){y.__e(i,e)}r.base=r.__P=r.__n=null}if(r=n.__k)for(s=0;s<r.length;s++)r[s]&&ut(r[s],e,t||typeof n.type!="function");t||Ae(n.__e),n.__c=n.__=n.__e=void 0}function Xt(n,e,t){return this.constructor(n,t)}function Qt(n,e,t){var r,s,i,o;e==document&&(e=document.documentElement),y.__&&y.__(n,e),s=(r=!1)?null:e.__k,i=[],o=[],Oe(e,n=e.__k=tt(j,null,[n]),s||se,se,e.namespaceURI,s?null:e.firstChild?ne.call(e.childNodes):null,i,s?s.__e:e.firstChild,r,o),lt(i,n,o),n.props.children=null}ne=ie.slice,y={__e:function(n,e,t,r){for(var s,i,o;e=e.__;)if((s=e.__c)&&!s.__)try{if((i=s.constructor)&&i.getDerivedStateFromError!=null&&(s.setState(i.getDerivedStateFromError(n)),o=s.__d),s.componentDidCatch!=null&&(s.componentDidCatch(n,r||{}),o=s.__d),o)return s.__E=s}catch(c){n=c}throw n}},Xe=0,ce.prototype.setState=function(n,e){var t;t=this.__s!=null&&this.__s!=this.state?this.__s:this.__s=M({},this.state),typeof n=="function"&&(n=n(M({},t),this.props)),n&&M(t,n),n!=null&&this.__v&&(e&&this._sb.push(e),rt(this))},ce.prototype.forceUpdate=function(n){this.__v&&(this.__e=!0,n&&this.__h.push(n),rt(this))},ce.prototype.render=j,F=[],Ge=typeof Promise=="function"?Promise.prototype.then.bind(Promise.resolve()):setTimeout,Ze=function(n,e){return n.__v.__b-e.__v.__b},le.__r=0,Ee=Math.random().toString(8),re="__d"+Ee,G="__a"+Ee,et=/(PointerCapture)$|Capture$/i,Se=0,Ce=at(!1),Te=at(!0);var Gt=0;function u(n,e,t,r,s,i){e||(e={});var o,c,h=e;if("ref"in h)for(c in h={},e)c=="ref"?o=e[c]:h[c]=e[c];var l={type:n,props:h,key:t,ref:o,__k:null,__:null,__b:0,__e:null,__c:null,constructor:void 0,__v:--Gt,__i:-1,__u:0,__source:s,__self:i};if(typeof n=="function"&&(o=n.defaultProps))for(c in o)h[c]===void 0&&(h[c]=o[c]);return y.vnode&&y.vnode(l),l}var Z,S,Re,ft,ue=0,dt=[],T=y,pt=T.__b,_t=T.__r,gt=T.diffed,mt=T.__c,bt=T.unmount,yt=T.__;function Ne(n,e){T.__h&&T.__h(S,n,ue||e),ue=0;var t=S.__H||(S.__H={__:[],__h:[]});return n>=t.__.length&&t.__.push({}),t.__[n]}function L(n){return ue=1,Zt(kt,n)}function Zt(n,e,t){var r=Ne(Z++,2);if(r.t=n,!r.__c&&(r.__=[kt(void 0,e),function(c){var h=r.__N?r.__N[0]:r.__[0],l=r.t(h,c);h!==l&&(r.__N=[l,r.__[1]],r.__c.setState({}))}],r.__c=S,!S.__f)){var s=function(c,h,l){if(!r.__c.__H)return!0;var d=!1,_=r.__c.props!==c;if(r.__c.__H.__.some(function(p){if(p.__N){d=!0;var v=p.__[0];p.__=p.__N,p.__N=void 0,v!==p.__[0]&&(_=!0)}}),i){var a=i.call(this,c,h,l);return d?a||_:a}return!d||_};S.__f=!0;var i=S.shouldComponentUpdate,o=S.componentWillUpdate;S.componentWillUpdate=function(c,h,l){if(this.__e){var d=i;i=void 0,s(c,h,l),i=d}o&&o.call(this,c,h,l)},S.shouldComponentUpdate=s}return r.__N||r.__}function vt(n,e){var t=Ne(Z++,3);!T.__s&&xt(t.__H,e)&&(t.__=n,t.u=e,S.__H.__h.push(t))}function fe(n){return ue=5,en(function(){return{current:n}},[])}function en(n,e){var t=Ne(Z++,7);return xt(t.__H,e)&&(t.__=n(),t.__H=e,t.__h=n),t.__}function tn(){for(var n;n=dt.shift();){var e=n.__H;if(n.__P&&e)try{e.__h.some(de),e.__h.some(Le),e.__h=[]}catch(t){e.__h=[],T.__e(t,n.__v)}}}T.__b=function(n){S=null,pt&&pt(n)},T.__=function(n,e){n&&e.__k&&e.__k.__m&&(n.__m=e.__k.__m),yt&&yt(n,e)},T.__r=function(n){_t&&_t(n),Z=0;var e=(S=n.__c).__H;e&&(Re===S?(e.__h=[],S.__h=[],e.__.some(function(t){t.__N&&(t.__=t.__N),t.u=t.__N=void 0})):(e.__h.some(de),e.__h.some(Le),e.__h=[],Z=0)),Re=S},T.diffed=function(n){gt&&gt(n);var e=n.__c;e&&e.__H&&(e.__H.__h.length&&(dt.push(e)!==1&&ft===T.requestAnimationFrame||((ft=T.requestAnimationFrame)||nn)(tn)),e.__H.__.some(function(t){t.u&&(t.__H=t.u,t.u=void 0)})),Re=S=null},T.__c=function(n,e){e.some(function(t){try{t.__h.some(de),t.__h=t.__h.filter(function(r){return!r.__||Le(r)})}catch(r){e.some(function(s){s.__h&&(s.__h=[])}),e=[],T.__e(r,t.__v)}}),mt&&mt(n,e)},T.unmount=function(n){bt&&bt(n);var e,t=n.__c;t&&t.__H&&(t.__H.__.some(function(r){try{de(r)}catch(s){e=s}}),t.__H=void 0,e&&T.__e(e,t.__v))};var wt=typeof requestAnimationFrame=="function";function nn(n){var e,t=function(){clearTimeout(r),wt&&cancelAnimationFrame(e),setTimeout(n)},r=setTimeout(t,35);wt&&(e=requestAnimationFrame(t))}function de(n){var e=S,t=n.__c;typeof t=="function"&&(n.__c=void 0,t()),S=e}function Le(n){var e=S;n.__c=n.__(),S=e}function xt(n,e){return!n||n.length!==e.length||e.some(function(t,r){return t!==n[r]})}function kt(n,e){return typeof e=="function"?e(n):e}function rn({config:n,onClick:e}){const t=n.position==="bottom-left"?"pos-left":"pos-right";return u("button",{class:`launcher ${t}`,onClick:e,"aria-label":"Open chat",type:"button",children:u("svg",{xmlns:"http://www.w3.org/2000/svg",viewBox:"0 0 24 24",fill:"none",stroke:"currentColor","stroke-width":"2","stroke-linecap":"round","stroke-linejoin":"round",children:u("path",{d:"M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"})})})}function sn({message:n,onSelect:e}){var l,d,_;const t=n.direction==="outbound",[r,s]=L(!1);if(n.sender==="system")return u("div",{class:"system-notice",children:u("span",{children:"You are now chatting with a staff member"})});const i=`bubble ${t?"user":n.sender==="staff"?"bot staff":"bot"}${n.optimistic?" optimistic":""}`,o=(!r&&((l=n.interactive)==null?void 0:l.type)==="list"?((_=(d=n.interactive.action)==null?void 0:d.sections)==null?void 0:_.flatMap(a=>a.rows??[]))??[]:[]).filter(a=>!!a.title);function c(a){s(!0),e==null||e(a)}const h=o.length>0&&u("div",{class:"suggestions",children:o.map(a=>u("button",{class:"suggestion-btn",type:"button",onClick:()=>c(a.title),children:a.title},a.id??a.title))});return!t&&n.streaming?u("div",{class:i,children:[n.body,u("span",{class:"streaming-cursor","aria-hidden":"true"})]}):!t&&n.html&&n.sender!=="staff"?u(j,{children:[u("div",{class:i,dangerouslySetInnerHTML:{__html:n.html}}),h]}):u(j,{children:[u("div",{class:i,children:[n.sender==="staff"&&u("span",{class:"staff-label",children:"Staff"}),n.body]}),h]})}function on(){return u("div",{class:"typing-indicator",children:[u("div",{class:"typing-dot"}),u("div",{class:"typing-dot"}),u("div",{class:"typing-dot"})]})}const an=[{code:"nl",label:"NL"},{code:"en",label:"EN"},{code:"fr",label:"FR"}],pe={nl:"U spreekt met een AI-assistent.",en:"You are chatting with an AI assistant.",fr:"Vous discutez avec un assistant IA."};function cn({config:n,phase:e,lang:t,messages:r,isTyping:s,inputValue:i,isSending:o,consentAccepted:c,onLangSelect:h,onPreChatSubmit:l,onAcceptConsent:d,onInputChange:_,onSend:a,onClose:p,onReset:v,onSuggestion:C,onSlotSelect:E}){const w=n.position==="bottom-left"?"pos-left":"pos-right",b=fe(null),[O,N]=L(""),[k,B]=L(""),[V,q]=L(""),[W,R]=L(!1);vt(()=>{var f;(f=b.current)==null||f.scrollIntoView({behavior:"smooth"})},[r.length,s]);function U(f){f.key==="Enter"&&!f.shiftKey&&(f.preventDefault(),i.trim()&&!o&&a())}const Je=n.greetingByLang[t]??n.greetingByLang.nl??Object.values(n.greetingByLang)[0]??"Welkom! Hoe kan ik u helpen? 👋",ke=n.suggestedQuestions??[];return u("div",{class:`chat-window ${w}${e!=="welcome"||r.length>0," open"}`,children:[u("div",{class:"header",children:[u("div",{class:"header-avatar",children:n.avatarUrl?u("img",{src:n.avatarUrl,alt:n.headerTitle}):u("svg",{xmlns:"http://www.w3.org/2000/svg",width:"20",height:"20",viewBox:"0 0 24 24",fill:"none",stroke:"#fff","stroke-width":"2","stroke-linecap":"round","stroke-linejoin":"round",children:u("path",{d:"M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"})})}),u("div",{class:"header-info",children:[u("span",{class:"header-title",children:n.headerTitle}),u("div",{class:"header-status",children:[u("span",{class:"status-dot"}),u("span",{children:"Online"})]})]}),e==="chat"&&u("button",{class:"reset-btn",onClick:v,type:"button","aria-label":"Start a new conversation",title:"Start a new conversation",children:u("svg",{xmlns:"http://www.w3.org/2000/svg",width:"17",height:"17",viewBox:"0 0 24 24",fill:"none",stroke:"#fff","stroke-width":"2","stroke-linecap":"round","stroke-linejoin":"round",children:[u("path",{d:"M3 2v6h6"}),u("path",{d:"M3 13a9 9 0 1 0 3-7.7L3 8"})]})}),u("button",{class:"close-btn",onClick:p,type:"button","aria-label":"Close",children:"×"})]}),e==="prechat"&&u("div",{class:"welcome",children:[u("div",{class:"welcome-icon",children:u("svg",{xmlns:"http://www.w3.org/2000/svg",viewBox:"0 0 24 24",fill:"none","stroke-width":"1.8","stroke-linecap":"round","stroke-linejoin":"round",children:[u("path",{d:"M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"}),u("circle",{cx:"12",cy:"7",r:"4"})]})}),u("h2",{class:"welcome-title",children:"Before we start"}),u("p",{class:"welcome-sub",children:"Leave your email so we can follow up if needed."}),u("div",{class:"prechat-form",children:[u("input",{class:"prechat-input",type:"text",placeholder:"Your name (optional)",value:k,onInput:f=>B(f.target.value)}),u("input",{class:"prechat-input",type:"email",placeholder:"Your email address *",value:O,onInput:f=>{N(f.target.value),q("")}}),V&&u("p",{class:"prechat-error",children:V}),u("button",{class:"prechat-submit",type:"button",disabled:W,onClick:async()=>{const f=O.trim();if(!f||!f.includes("@")){q("Please enter a valid email address.");return}R(!0),await l(f,k.trim()||void 0),R(!1)},children:W?"…":"Start chat →"}),u("button",{class:"prechat-skip",type:"button",onClick:()=>l("",void 0),children:"Skip"})]})]}),e==="welcome"&&u("div",{class:"welcome",children:[u("div",{class:"welcome-icon",children:u("svg",{xmlns:"http://www.w3.org/2000/svg",viewBox:"0 0 24 24",fill:"none","stroke-width":"1.8","stroke-linecap":"round","stroke-linejoin":"round",children:u("path",{d:"M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"})})}),u("h2",{class:"welcome-title",children:Je}),u("p",{class:"ai-notice",children:["🤖 ",pe[t]??pe.en]}),u("p",{class:"welcome-sub",children:n.responseTimeText??"Choose your language to get started."}),u("div",{class:"lang-picker",children:an.map(f=>u("button",{class:`lang-btn${t===f.code?" selected":""}`,type:"button",onClick:()=>h(f.code),children:f.label},f.code))})]}),u("div",{class:`chat-body${e==="chat"?" active":""}`,children:[e==="chat"&&u("div",{class:"ai-notice-strip",children:["🤖 ",pe[t]??pe.en]}),u("div",{class:"messages",children:[r.length===0&&ke.length>0&&u("div",{class:"suggestions",children:ke.map(f=>u("button",{class:"suggestion-btn",type:"button",onClick:()=>C(f),children:f},f))}),r.map(f=>u(sn,{message:f,onSelect:E},f.id)),s&&u(on,{}),u("div",{ref:b})]}),u("div",{class:"controls",children:[u("textarea",{class:"textarea",rows:1,placeholder:"Type a message…",value:i,onInput:f=>{const g=f.target;_(g.value),g.style.height="auto",g.style.height=Math.min(g.scrollHeight,120)+"px"},onKeyDown:U,disabled:o}),u("button",{class:"send-btn",type:"button",onClick:a,disabled:!i.trim()||o,"aria-label":"Send",children:u("svg",{xmlns:"http://www.w3.org/2000/svg",viewBox:"0 0 24 24",fill:"none",stroke:"currentColor","stroke-width":"2.2","stroke-linecap":"round","stroke-linejoin":"round",children:[u("line",{x1:"22",y1:"2",x2:"11",y2:"13"}),u("polygon",{points:"22 2 15 22 11 13 2 9 22 2"})]})})]}),!c&&u("div",{class:"consent-banner",children:[u("span",{children:"We store your chat to help with follow-ups."}),u("button",{class:"consent-accept",type:"button",onClick:d,children:"OK"})]}),n.poweredByVisible&&u("div",{class:"footer",children:u("a",{href:"https://genaitech.be",target:"_blank",rel:"noopener noreferrer",children:"Powered by GenAITech"})})]})]})}const Ie=n=>`_cw_conversation_${n}`;function ln(n){try{return localStorage.getItem(Ie(n))}catch{return null}}function Et(n,e){try{localStorage.setItem(Ie(n),e)}catch{}}function hn(n){try{localStorage.removeItem(Ie(n))}catch{}}const D=Object.create(null);D.open="0",D.close="1",D.ping="2",D.pong="3",D.message="4",D.upgrade="5",D.noop="6";const _e=Object.create(null);Object.keys(D).forEach(n=>{_e[D[n]]=n});const Pe={type:"error",data:"parser error"},St=typeof Blob=="function"||typeof Blob<"u"&&Object.prototype.toString.call(Blob)==="[object BlobConstructor]",Ct=typeof ArrayBuffer=="function",Tt=n=>typeof ArrayBuffer.isView=="function"?ArrayBuffer.isView(n):n&&n.buffer instanceof ArrayBuffer,De=({type:n,data:e},t,r)=>St&&e instanceof Blob?t?r(e):At(e,r):Ct&&(e instanceof ArrayBuffer||Tt(e))?t?r(e):At(new Blob([e]),r):r(D[n]+(e||"")),At=(n,e)=>{const t=new FileReader;return t.onload=function(){const r=t.result.split(",")[1];e("b"+(r||""))},t.readAsDataURL(n)};function Ot(n){return n instanceof Uint8Array?n:n instanceof ArrayBuffer?new Uint8Array(n):new Uint8Array(n.buffer,n.byteOffset,n.byteLength)}let $e;function un(n,e){if(St&&n.data instanceof Blob)return n.data.arrayBuffer().then(Ot).then(e);if(Ct&&(n.data instanceof ArrayBuffer||Tt(n.data)))return e(Ot(n.data));De(n,!1,t=>{$e||($e=new TextEncoder),e($e.encode(t))})}const Bt="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/",ee=typeof Uint8Array>"u"?[]:new Uint8Array(256);for(let n=0;n<Bt.length;n++)ee[Bt.charCodeAt(n)]=n;const fn=n=>{let e=n.length*.75,t=n.length,r,s=0,i,o,c,h;n[n.length-1]==="="&&(e--,n[n.length-2]==="="&&e--);const l=new ArrayBuffer(e),d=new Uint8Array(l);for(r=0;r<t;r+=4)i=ee[n.charCodeAt(r)],o=ee[n.charCodeAt(r+1)],c=ee[n.charCodeAt(r+2)],h=ee[n.charCodeAt(r+3)],d[s++]=i<<2|o>>4,d[s++]=(o&15)<<4|c>>2,d[s++]=(c&3)<<6|h&63;return l},dn=typeof ArrayBuffer=="function",qe=(n,e)=>{if(typeof n!="string")return{type:"message",data:Rt(n,e)};const t=n.charAt(0);return t==="b"?{type:"message",data:pn(n.substring(1),e)}:_e[t]?n.length>1?{type:_e[t],data:n.substring(1)}:{type:_e[t]}:Pe},pn=(n,e)=>{if(dn){const t=fn(n);return Rt(t,e)}else return{base64:!0,data:n}},Rt=(n,e)=>{switch(e){case"blob":return n instanceof Blob?n:new Blob([n]);case"arraybuffer":default:return n instanceof ArrayBuffer?n:n.buffer}},Nt="",_n=(n,e)=>{const t=n.length,r=new Array(t);let s=0;n.forEach((i,o)=>{De(i,!1,c=>{r[o]=c,++s===t&&e(r.join(Nt))})})},gn=(n,e)=>{const t=n.split(Nt),r=[];for(let s=0;s<t.length;s++){const i=qe(t[s],e);if(r.push(i),i.type==="error")break}return r};function mn(){return new TransformStream({transform(n,e){un(n,t=>{const r=t.length;let s;if(r<126)s=new Uint8Array(1),new DataView(s.buffer).setUint8(0,r);else if(r<65536){s=new Uint8Array(3);const i=new DataView(s.buffer);i.setUint8(0,126),i.setUint16(1,r)}else{s=new Uint8Array(9);const i=new DataView(s.buffer);i.setUint8(0,127),i.setBigUint64(1,BigInt(r))}n.data&&typeof n.data!="string"&&(s[0]|=128),e.enqueue(s),e.enqueue(t)})}})}let Ue;function ge(n){return n.reduce((e,t)=>e+t.length,0)}function me(n,e){if(n[0].length===e)return n.shift();const t=new Uint8Array(e);let r=0;for(let s=0;s<e;s++)t[s]=n[0][r++],r===n[0].length&&(n.shift(),r=0);return n.length&&r<n[0].length&&(n[0]=n[0].slice(r)),t}function bn(n,e){Ue||(Ue=new TextDecoder);const t=[];let r=0,s=-1,i=!1;return new TransformStream({transform(o,c){for(t.push(o);;){if(r===0){if(ge(t)<1)break;const h=me(t,1);i=(h[0]&128)===128,s=h[0]&127,s<126?r=3:s===126?r=1:r=2}else if(r===1){if(ge(t)<2)break;const h=me(t,2);s=new DataView(h.buffer,h.byteOffset,h.length).getUint16(0),r=3}else if(r===2){if(ge(t)<8)break;const h=me(t,8),l=new DataView(h.buffer,h.byteOffset,h.length),d=l.getUint32(0);if(d>Math.pow(2,21)-1){c.enqueue(Pe);break}s=d*Math.pow(2,32)+l.getUint32(4),r=3}else{if(ge(t)<s)break;const h=me(t,s);c.enqueue(qe(i?h:Ue.decode(h),e)),r=0}if(s===0||s>n){c.enqueue(Pe);break}}}})}const Lt=4;function A(n){if(n)return yn(n)}function yn(n){for(var e in A.prototype)n[e]=A.prototype[e];return n}A.prototype.on=A.prototype.addEventListener=function(n,e){return this._callbacks=this._callbacks||{},(this._callbacks["$"+n]=this._callbacks["$"+n]||[]).push(e),this},A.prototype.once=function(n,e){function t(){this.off(n,t),e.apply(this,arguments)}return t.fn=e,this.on(n,t),this},A.prototype.off=A.prototype.removeListener=A.prototype.removeAllListeners=A.prototype.removeEventListener=function(n,e){if(this._callbacks=this._callbacks||{},arguments.length==0)return this._callbacks={},this;var t=this._callbacks["$"+n];if(!t)return this;if(arguments.length==1)return delete this._callbacks["$"+n],this;for(var r,s=0;s<t.length;s++)if(r=t[s],r===e||r.fn===e){t.splice(s,1);break}return t.length===0&&delete this._callbacks["$"+n],this},A.prototype.emit=function(n){this._callbacks=this._callbacks||{};for(var e=new Array(arguments.length-1),t=this._callbacks["$"+n],r=1;r<arguments.length;r++)e[r-1]=arguments[r];if(t){t=t.slice(0);for(var r=0,s=t.length;r<s;++r)t[r].apply(this,e)}return this},A.prototype.emitReserved=A.prototype.emit,A.prototype.listeners=function(n){return this._callbacks=this._callbacks||{},this._callbacks["$"+n]||[]},A.prototype.hasListeners=function(n){return!!this.listeners(n).length};const be=typeof Promise=="function"&&typeof Promise.resolve=="function"?e=>Promise.resolve().then(e):(e,t)=>t(e,0),I=typeof self<"u"?self:typeof window<"u"?window:Function("return this")(),vn="arraybuffer";function pr(){}function It(n,...e){return e.reduce((t,r)=>(n.hasOwnProperty(r)&&(t[r]=n[r]),t),{})}const wn=I.setTimeout,xn=I.clearTimeout;function ye(n,e){e.useNativeTimers?(n.setTimeoutFn=wn.bind(I),n.clearTimeoutFn=xn.bind(I)):(n.setTimeoutFn=I.setTimeout.bind(I),n.clearTimeoutFn=I.clearTimeout.bind(I))}const kn=1.33;function En(n){return typeof n=="string"?Sn(n):Math.ceil((n.byteLength||n.size)*kn)}function Sn(n){let e=0,t=0;for(let r=0,s=n.length;r<s;r++)e=n.charCodeAt(r),e<128?t+=1:e<2048?t+=2:e<55296||e>=57344?t+=3:(r++,t+=4);return t}function Pt(){return Date.now().toString(36).substring(3)+Math.random().toString(36).substring(2,5)}function Cn(n){let e="";for(let t in n)n.hasOwnProperty(t)&&(e.length&&(e+="&"),e+=encodeURIComponent(t)+"="+encodeURIComponent(n[t]));return e}function Tn(n){let e={},t=n.split("&");for(let r=0,s=t.length;r<s;r++){let i=t[r].split("=");e[decodeURIComponent(i[0])]=decodeURIComponent(i[1])}return e}class An extends Error{constructor(e,t,r){super(e),this.description=t,this.context=r,this.type="TransportError"}}class Me extends A{constructor(e){super(),this.writable=!1,ye(this,e),this.opts=e,this.query=e.query,this.socket=e.socket,this.supportsBinary=!e.forceBase64}onError(e,t,r){return super.emitReserved("error",new An(e,t,r)),this}open(){return this.readyState="opening",this.doOpen(),this}close(){return(this.readyState==="opening"||this.readyState==="open")&&(this.doClose(),this.onClose()),this}send(e){this.readyState==="open"&&this.write(e)}onOpen(){this.readyState="open",this.writable=!0,super.emitReserved("open")}onData(e){const t=qe(e,this.socket.binaryType);this.onPacket(t)}onPacket(e){super.emitReserved("packet",e)}onClose(e){this.readyState="closed",super.emitReserved("close",e)}pause(e){}createUri(e,t={}){return e+"://"+this._hostname()+this._port()+this.opts.path+this._query(t)}_hostname(){const e=this.opts.hostname;return e.indexOf(":")===-1?e:"["+e+"]"}_port(){return this.opts.port&&(this.opts.secure&&Number(this.opts.port)!==443||!this.opts.secure&&Number(this.opts.port)!==80)?":"+this.opts.port:""}_query(e){const t=Cn(e);return t.length?"?"+t:""}}class On extends Me{constructor(){super(...arguments),this._polling=!1}get name(){return"polling"}doOpen(){this._poll()}pause(e){this.readyState="pausing";const t=()=>{this.readyState="paused",e()};if(this._polling||!this.writable){let r=0;this._polling&&(r++,this.once("pollComplete",function(){--r||t()})),this.writable||(r++,this.once("drain",function(){--r||t()}))}else t()}_poll(){this._polling=!0,this.doPoll(),this.emitReserved("poll")}onData(e){const t=r=>{if(this.readyState==="opening"&&r.type==="open"&&this.onOpen(),r.type==="close")return this.onClose({description:"transport closed by the server"}),!1;this.onPacket(r)};gn(e,this.socket.binaryType).forEach(t),this.readyState!=="closed"&&(this._polling=!1,this.emitReserved("pollComplete"),this.readyState==="open"&&this._poll())}doClose(){const e=()=>{this.write([{type:"close"}])};this.readyState==="open"?e():this.once("open",e)}write(e){this.writable=!1,_n(e,t=>{this.doWrite(t,()=>{this.writable=!0,this.emitReserved("drain")})})}uri(){const e=this.opts.secure?"https":"http",t=this.query||{};return this.opts.timestampRequests!==!1&&(t[this.opts.timestampParam]=Pt()),!this.supportsBinary&&!t.sid&&(t.b64=1),this.createUri(e,t)}}let Dt=!1;try{Dt=typeof XMLHttpRequest<"u"&&"withCredentials"in new XMLHttpRequest}catch{}const Bn=Dt;function Rn(){}class Nn extends On{constructor(e){if(super(e),typeof location<"u"){const t=location.protocol==="https:";let r=location.port;r||(r=t?"443":"80"),this.xd=typeof location<"u"&&e.hostname!==location.hostname||r!==e.port}}doWrite(e,t){const r=this.request({method:"POST",data:e});r.on("success",t),r.on("error",(s,i)=>{this.onError("xhr post error",s,i)})}doPoll(){const e=this.request();e.on("data",this.onData.bind(this)),e.on("error",(t,r)=>{this.onError("xhr poll error",t,r)}),this.pollXhr=e}}class $ extends A{constructor(e,t,r){super(),this.createRequest=e,ye(this,r),this._opts=r,this._method=r.method||"GET",this._uri=t,this._data=r.data!==void 0?r.data:null,this._create()}_create(){var e;const t=It(this._opts,"agent","pfx","key","passphrase","cert","ca","ciphers","rejectUnauthorized","autoUnref");t.xdomain=!!this._opts.xd;const r=this._xhr=this.createRequest(t);try{r.open(this._method,this._uri,!0);try{if(this._opts.extraHeaders){r.setDisableHeaderCheck&&r.setDisableHeaderCheck(!0);for(let s in this._opts.extraHeaders)this._opts.extraHeaders.hasOwnProperty(s)&&r.setRequestHeader(s,this._opts.extraHeaders[s])}}catch{}if(this._method==="POST")try{r.setRequestHeader("Content-type","text/plain;charset=UTF-8")}catch{}try{r.setRequestHeader("Accept","*/*")}catch{}(e=this._opts.cookieJar)===null||e===void 0||e.addCookies(r),"withCredentials"in r&&(r.withCredentials=this._opts.withCredentials),this._opts.requestTimeout&&(r.timeout=this._opts.requestTimeout),r.onreadystatechange=()=>{var s;r.readyState===3&&((s=this._opts.cookieJar)===null||s===void 0||s.parseCookies(r.getResponseHeader("set-cookie"))),r.readyState===4&&(r.status===200||r.status===1223?this._onLoad():this.setTimeoutFn(()=>{this._onError(typeof r.status=="number"?r.status:0)},0))},r.send(this._data)}catch(s){this.setTimeoutFn(()=>{this._onError(s)},0);return}typeof document<"u"&&(this._index=$.requestsCount++,$.requests[this._index]=this)}_onError(e){this.emitReserved("error",e,this._xhr),this._cleanup(!0)}_cleanup(e){if(!(typeof this._xhr>"u"||this._xhr===null)){if(this._xhr.onreadystatechange=Rn,e)try{this._xhr.abort()}catch{}typeof document<"u"&&delete $.requests[this._index],this._xhr=null}}_onLoad(){const e=this._xhr.responseText;e!==null&&(this.emitReserved("data",e),this.emitReserved("success"),this._cleanup())}abort(){this._cleanup()}}if($.requestsCount=0,$.requests={},typeof document<"u"){if(typeof attachEvent=="function")attachEvent("onunload",$t);else if(typeof addEventListener=="function"){const n="onpagehide"in I?"pagehide":"unload";addEventListener(n,$t,!1)}}function $t(){for(let n in $.requests)$.requests.hasOwnProperty(n)&&$.requests[n].abort()}const Ln=(function(){const n=qt({xdomain:!1});return n&&n.responseType!==null})();class In extends Nn{constructor(e){super(e);const t=e&&e.forceBase64;this.supportsBinary=Ln&&!t}request(e={}){return Object.assign(e,{xd:this.xd},this.opts),new $(qt,this.uri(),e)}}function qt(n){const e=n.xdomain;try{if(typeof XMLHttpRequest<"u"&&(!e||Bn))return new XMLHttpRequest}catch{}if(!e)try{return new I[["Active"].concat("Object").join("X")]("Microsoft.XMLHTTP")}catch{}}const Ut=typeof navigator<"u"&&typeof navigator.product=="string"&&navigator.product.toLowerCase()==="reactnative";class Pn extends Me{get name(){return"websocket"}doOpen(){const e=this.uri(),t=this.opts.protocols,r=Ut?{}:It(this.opts,"agent","perMessageDeflate","pfx","key","passphrase","cert","ca","ciphers","rejectUnauthorized","localAddress","protocolVersion","origin","maxPayload","family","checkServerIdentity");this.opts.extraHeaders&&(r.headers=this.opts.extraHeaders);try{this.ws=this.createSocket(e,t,r)}catch(s){return this.emitReserved("error",s)}this.ws.binaryType=this.socket.binaryType,this.addEventListeners()}addEventListeners(){this.ws.onopen=()=>{this.opts.autoUnref&&this.ws._socket.unref(),this.onOpen()},this.ws.onclose=e=>this.onClose({description:"websocket connection closed",context:e}),this.ws.onmessage=e=>this.onData(e.data),this.ws.onerror=e=>this.onError("websocket error",e)}write(e){this.writable=!1;for(let t=0;t<e.length;t++){const r=e[t],s=t===e.length-1;De(r,this.supportsBinary,i=>{try{this.doWrite(r,i)}catch{}s&&be(()=>{this.writable=!0,this.emitReserved("drain")},this.setTimeoutFn)})}}doClose(){typeof this.ws<"u"&&(this.ws.onerror=()=>{},this.ws.close(),this.ws=null)}uri(){const e=this.opts.secure?"wss":"ws",t=this.query||{};return this.opts.timestampRequests&&(t[this.opts.timestampParam]=Pt()),this.supportsBinary||(t.b64=1),this.createUri(e,t)}}const He=I.WebSocket||I.MozWebSocket;class Dn extends Pn{createSocket(e,t,r){return Ut?new He(e,t,r):t?new He(e,t):new He(e)}doWrite(e,t){this.ws.send(t)}}class $n extends Me{get name(){return"webtransport"}doOpen(){try{this._transport=new WebTransport(this.createUri("https"),this.opts.transportOptions[this.name])}catch(e){return this.emitReserved("error",e)}this._transport.closed.then(()=>{this.onClose()}).catch(e=>{this.onError("webtransport error",e)}),this._transport.ready.then(()=>{this._transport.createBidirectionalStream().then(e=>{const t=bn(Number.MAX_SAFE_INTEGER,this.socket.binaryType),r=e.readable.pipeThrough(t).getReader(),s=mn();s.readable.pipeTo(e.writable),this._writer=s.writable.getWriter();const i=()=>{r.read().then(({done:c,value:h})=>{c||(this.onPacket(h),i())}).catch(c=>{})};i();const o={type:"open"};this.query.sid&&(o.data=`{"sid":"${this.query.sid}"}`),this._writer.write(o).then(()=>this.onOpen())})})}write(e){this.writable=!1;for(let t=0;t<e.length;t++){const r=e[t],s=t===e.length-1;this._writer.write(r).then(()=>{s&&be(()=>{this.writable=!0,this.emitReserved("drain")},this.setTimeoutFn)})}}doClose(){var e;(e=this._transport)===null||e===void 0||e.close()}}const qn={websocket:Dn,webtransport:$n,polling:In},Un=/^(?:(?![^:@\/?#]+:[^:@\/]*@)(http|https|ws|wss):\/\/)?((?:(([^:@\/?#]*)(?::([^:@\/?#]*))?)?@)?((?:[a-f0-9]{0,4}:){2,7}[a-f0-9]{0,4}|[^:\/?#]*)(?::(\d*))?)(((\/(?:[^?#](?![^?#\/]*\.[^?#\/.]+(?:[?#]|$)))*\/?)?([^?#\/]*))(?:\?([^#]*))?(?:#(.*))?)/,Mn=["source","protocol","authority","userInfo","user","password","host","port","relative","path","directory","file","query","anchor"];function Fe(n){if(n.length>8e3)throw"URI too long";const e=n,t=n.indexOf("["),r=n.indexOf("]");t!=-1&&r!=-1&&(n=n.substring(0,t)+n.substring(t,r).replace(/:/g,";")+n.substring(r,n.length));let s=Un.exec(n||""),i={},o=14;for(;o--;)i[Mn[o]]=s[o]||"";return t!=-1&&r!=-1&&(i.source=e,i.host=i.host.substring(1,i.host.length-1).replace(/;/g,":"),i.authority=i.authority.replace("[","").replace("]","").replace(/;/g,":"),i.ipv6uri=!0),i.pathNames=Hn(i,i.path),i.queryKey=Fn(i,i.query),i}function Hn(n,e){const t=/\/{2,9}/g,r=e.replace(t,"/").split("/");return(e.slice(0,1)=="/"||e.length===0)&&r.splice(0,1),e.slice(-1)=="/"&&r.splice(r.length-1,1),r}function Fn(n,e){const t={};return e.replace(/(?:^|&)([^&=]*)=?([^&]*)/g,function(r,s,i){s&&(t[s]=i)}),t}const ze=typeof addEventListener=="function"&&typeof removeEventListener=="function",ve=[];ze&&addEventListener("offline",()=>{ve.forEach(n=>n())},!1);class z extends A{constructor(e,t){if(super(),this.binaryType=vn,this.writeBuffer=[],this._prevBufferLen=0,this._pingInterval=-1,this._pingTimeout=-1,this._maxPayload=-1,this._pingTimeoutTime=1/0,e&&typeof e=="object"&&(t=e,e=null),e){const r=Fe(e);t.hostname=r.host,t.secure=r.protocol==="https"||r.protocol==="wss",t.port=r.port,r.query&&(t.query=r.query)}else t.host&&(t.hostname=Fe(t.host).host);ye(this,t),this.secure=t.secure!=null?t.secure:typeof location<"u"&&location.protocol==="https:",t.hostname&&!t.port&&(t.port=this.secure?"443":"80"),this.hostname=t.hostname||(typeof location<"u"?location.hostname:"localhost"),this.port=t.port||(typeof location<"u"&&location.port?location.port:this.secure?"443":"80"),this.transports=[],this._transportsByName={},t.transports.forEach(r=>{const s=r.prototype.name;this.transports.push(s),this._transportsByName[s]=r}),this.opts=Object.assign({path:"/engine.io",agent:!1,withCredentials:!1,upgrade:!0,timestampParam:"t",rememberUpgrade:!1,addTrailingSlash:!0,rejectUnauthorized:!0,perMessageDeflate:{threshold:1024},transportOptions:{},closeOnBeforeunload:!1},t),this.opts.path=this.opts.path.replace(/\/$/,"")+(this.opts.addTrailingSlash?"/":""),typeof this.opts.query=="string"&&(this.opts.query=Tn(this.opts.query)),ze&&(this.opts.closeOnBeforeunload&&(this._beforeunloadEventListener=()=>{this.transport&&(this.transport.removeAllListeners(),this.transport.close())},addEventListener("beforeunload",this._beforeunloadEventListener,!1)),this.hostname!=="localhost"&&(this._offlineEventListener=()=>{this._onClose("transport close",{description:"network connection lost"})},ve.push(this._offlineEventListener))),this.opts.withCredentials&&(this._cookieJar=void 0),this._open()}createTransport(e){const t=Object.assign({},this.opts.query);t.EIO=Lt,t.transport=e,this.id&&(t.sid=this.id);const r=Object.assign({},this.opts,{query:t,socket:this,hostname:this.hostname,secure:this.secure,port:this.port},this.opts.transportOptions[e]);return new this._transportsByName[e](r)}_open(){if(this.transports.length===0){this.setTimeoutFn(()=>{this.emitReserved("error","No transports available")},0);return}const e=this.opts.rememberUpgrade&&z.priorWebsocketSuccess&&this.transports.indexOf("websocket")!==-1?"websocket":this.transports[0];this.readyState="opening";const t=this.createTransport(e);t.open(),this.setTransport(t)}setTransport(e){this.transport&&this.transport.removeAllListeners(),this.transport=e,e.on("drain",this._onDrain.bind(this)).on("packet",this._onPacket.bind(this)).on("error",this._onError.bind(this)).on("close",t=>this._onClose("transport close",t))}onOpen(){this.readyState="open",z.priorWebsocketSuccess=this.transport.name==="websocket",this.emitReserved("open"),this.flush()}_onPacket(e){if(this.readyState==="opening"||this.readyState==="open"||this.readyState==="closing")switch(this.emitReserved("packet",e),this.emitReserved("heartbeat"),e.type){case"open":this.onHandshake(JSON.parse(e.data));break;case"ping":this._sendPacket("pong"),this.emitReserved("ping"),this.emitReserved("pong"),this._resetPingTimeout();break;case"error":const t=new Error("server error");t.code=e.data,this._onError(t);break;case"message":this.emitReserved("data",e.data),this.emitReserved("message",e.data);break}}onHandshake(e){this.emitReserved("handshake",e),this.id=e.sid,this.transport.query.sid=e.sid,this._pingInterval=e.pingInterval,this._pingTimeout=e.pingTimeout,this._maxPayload=e.maxPayload,this.onOpen(),this.readyState!=="closed"&&this._resetPingTimeout()}_resetPingTimeout(){this.clearTimeoutFn(this._pingTimeoutTimer);const e=this._pingInterval+this._pingTimeout;this._pingTimeoutTime=Date.now()+e,this._pingTimeoutTimer=this.setTimeoutFn(()=>{this._onClose("ping timeout")},e),this.opts.autoUnref&&this._pingTimeoutTimer.unref()}_onDrain(){this.writeBuffer.splice(0,this._prevBufferLen),this._prevBufferLen=0,this.writeBuffer.length===0?this.emitReserved("drain"):this.flush()}flush(){if(this.readyState!=="closed"&&this.transport.writable&&!this.upgrading&&this.writeBuffer.length){const e=this._getWritablePackets();this.transport.send(e),this._prevBufferLen=e.length,this.emitReserved("flush")}}_getWritablePackets(){if(!(this._maxPayload&&this.transport.name==="polling"&&this.writeBuffer.length>1))return this.writeBuffer;let t=1;for(let r=0;r<this.writeBuffer.length;r++){const s=this.writeBuffer[r].data;if(s&&(t+=En(s)),r>0&&t>this._maxPayload)return this.writeBuffer.slice(0,r);t+=2}return this.writeBuffer}_hasPingExpired(){if(!this._pingTimeoutTime)return!0;const e=Date.now()>this._pingTimeoutTime;return e&&(this._pingTimeoutTime=0,be(()=>{this._onClose("ping timeout")},this.setTimeoutFn)),e}write(e,t,r){return this._sendPacket("message",e,t,r),this}send(e,t,r){return this._sendPacket("message",e,t,r),this}_sendPacket(e,t,r,s){if(typeof t=="function"&&(s=t,t=void 0),typeof r=="function"&&(s=r,r=null),this.readyState==="closing"||this.readyState==="closed")return;r=r||{},r.compress=r.compress!==!1;const i={type:e,data:t,options:r};this.emitReserved("packetCreate",i),this.writeBuffer.push(i),s&&this.once("flush",s),this.flush()}close(){const e=()=>{this._onClose("forced close"),this.transport.close()},t=()=>{this.off("upgrade",t),this.off("upgradeError",t),e()},r=()=>{this.once("upgrade",t),this.once("upgradeError",t)};return(this.readyState==="opening"||this.readyState==="open")&&(this.readyState="closing",this.writeBuffer.length?this.once("drain",()=>{this.upgrading?r():e()}):this.upgrading?r():e()),this}_onError(e){if(z.priorWebsocketSuccess=!1,this.opts.tryAllTransports&&this.transports.length>1&&this.readyState==="opening")return this.transports.shift(),this._open();this.emitReserved("error",e),this._onClose("transport error",e)}_onClose(e,t){if(this.readyState==="opening"||this.readyState==="open"||this.readyState==="closing"){if(this.clearTimeoutFn(this._pingTimeoutTimer),this.transport.removeAllListeners("close"),this.transport.close(),this.transport.removeAllListeners(),ze&&(this._beforeunloadEventListener&&removeEventListener("beforeunload",this._beforeunloadEventListener,!1),this._offlineEventListener)){const r=ve.indexOf(this._offlineEventListener);r!==-1&&ve.splice(r,1)}this.readyState="closed",this.id=null,this.emitReserved("close",e,t),this.writeBuffer=[],this._prevBufferLen=0}}}z.protocol=Lt;class zn extends z{constructor(){super(...arguments),this._upgrades=[]}onOpen(){if(super.onOpen(),this.readyState==="open"&&this.opts.upgrade)for(let e=0;e<this._upgrades.length;e++)this._probe(this._upgrades[e])}_probe(e){let t=this.createTransport(e),r=!1;z.priorWebsocketSuccess=!1;const s=()=>{r||(t.send([{type:"ping",data:"probe"}]),t.once("packet",_=>{if(!r)if(_.type==="pong"&&_.data==="probe"){if(this.upgrading=!0,this.emitReserved("upgrading",t),!t)return;z.priorWebsocketSuccess=t.name==="websocket",this.transport.pause(()=>{r||this.readyState!=="closed"&&(d(),this.setTransport(t),t.send([{type:"upgrade"}]),this.emitReserved("upgrade",t),t=null,this.upgrading=!1,this.flush())})}else{const a=new Error("probe error");a.transport=t.name,this.emitReserved("upgradeError",a)}}))};function i(){r||(r=!0,d(),t.close(),t=null)}const o=_=>{const a=new Error("probe error: "+_);a.transport=t.name,i(),this.emitReserved("upgradeError",a)};function c(){o("transport closed")}function h(){o("socket closed")}function l(_){t&&_.name!==t.name&&i()}const d=()=>{t.removeListener("open",s),t.removeListener("error",o),t.removeListener("close",c),this.off("close",h),this.off("upgrading",l)};t.once("open",s),t.once("error",o),t.once("close",c),this.once("close",h),this.once("upgrading",l),this._upgrades.indexOf("webtransport")!==-1&&e!=="webtransport"?this.setTimeoutFn(()=>{r||t.open()},200):t.open()}onHandshake(e){this._upgrades=this._filterUpgrades(e.upgrades),super.onHandshake(e)}_filterUpgrades(e){const t=[];for(let r=0;r<e.length;r++)~this.transports.indexOf(e[r])&&t.push(e[r]);return t}}let Vn=class extends zn{constructor(e,t={}){const r=typeof e=="object",s=r?{...e}:{...t};(!s.transports||s.transports&&typeof s.transports[0]=="string")&&(s.transports=(s.transports||["polling","websocket","webtransport"]).map(i=>qn[i]).filter(i=>!!i)),super(r?s:e,s)}};function Wn(n,e="",t){let r=n;t=t||typeof location<"u"&&location,n==null&&(n=t.protocol+"//"+t.host),typeof n=="string"&&(n.charAt(0)==="/"&&(n.charAt(1)==="/"?n=t.protocol+n:n=t.host+n),/^(https?|wss?):\/\//.test(n)||(typeof t<"u"?n=t.protocol+"//"+n:n="https://"+n),r=Fe(n)),r.port||(/^(http|ws)$/.test(r.protocol)?r.port="80":/^(http|ws)s$/.test(r.protocol)&&(r.port="443")),r.path=r.path||"/";const i=r.host.indexOf(":")!==-1?"["+r.host+"]":r.host;return r.id=r.protocol+"://"+i+":"+r.port+e,r.href=r.protocol+"://"+i+(t&&t.port===r.port?"":":"+r.port),r}const Yn=typeof ArrayBuffer=="function",jn=n=>typeof ArrayBuffer.isView=="function"?ArrayBuffer.isView(n):n.buffer instanceof ArrayBuffer,Mt=Object.prototype.toString,Kn=typeof Blob=="function"||typeof Blob<"u"&&Mt.call(Blob)==="[object BlobConstructor]",Jn=typeof File=="function"||typeof File<"u"&&Mt.call(File)==="[object FileConstructor]";function Ve(n){return Yn&&(n instanceof ArrayBuffer||jn(n))||Kn&&n instanceof Blob||Jn&&n instanceof File}function we(n,e){if(!n||typeof n!="object")return!1;if(Array.isArray(n)){for(let t=0,r=n.length;t<r;t++)if(we(n[t]))return!0;return!1}if(Ve(n))return!0;if(n.toJSON&&typeof n.toJSON=="function"&&arguments.length===1)return we(n.toJSON(),!0);for(const t in n)if(Object.prototype.hasOwnProperty.call(n,t)&&we(n[t]))return!0;return!1}function Xn(n){const e=[],t=n.data,r=n;return r.data=We(t,e),r.attachments=e.length,{packet:r,buffers:e}}function We(n,e){if(!n)return n;if(Ve(n)){const t={_placeholder:!0,num:e.length};return e.push(n),t}else if(Array.isArray(n)){const t=new Array(n.length);for(let r=0;r<n.length;r++)t[r]=We(n[r],e);return t}else if(typeof n=="object"&&!(n instanceof Date)){const t={};for(const r in n)Object.prototype.hasOwnProperty.call(n,r)&&(t[r]=We(n[r],e));return t}return n}function Qn(n,e){return n.data=Ye(n.data,e),delete n.attachments,n}function Ye(n,e){if(!n)return n;if(n&&n._placeholder===!0){if(typeof n.num=="number"&&n.num>=0&&n.num<e.length)return e[n.num];throw new Error("illegal attachments")}else if(Array.isArray(n))for(let t=0;t<n.length;t++)n[t]=Ye(n[t],e);else if(typeof n=="object")for(const t in n)Object.prototype.hasOwnProperty.call(n,t)&&(n[t]=Ye(n[t],e));return n}const Gn=["connect","connect_error","disconnect","disconnecting","newListener","removeListener"];var m;(function(n){n[n.CONNECT=0]="CONNECT",n[n.DISCONNECT=1]="DISCONNECT",n[n.EVENT=2]="EVENT",n[n.ACK=3]="ACK",n[n.CONNECT_ERROR=4]="CONNECT_ERROR",n[n.BINARY_EVENT=5]="BINARY_EVENT",n[n.BINARY_ACK=6]="BINARY_ACK"})(m||(m={}));class Zn{constructor(e){this.replacer=e}encode(e){return(e.type===m.EVENT||e.type===m.ACK)&&we(e)?this.encodeAsBinary({type:e.type===m.EVENT?m.BINARY_EVENT:m.BINARY_ACK,nsp:e.nsp,data:e.data,id:e.id}):[this.encodeAsString(e)]}encodeAsString(e){let t=""+e.type;return(e.type===m.BINARY_EVENT||e.type===m.BINARY_ACK)&&(t+=e.attachments+"-"),e.nsp&&e.nsp!=="/"&&(t+=e.nsp+","),e.id!=null&&(t+=e.id),e.data!=null&&(t+=JSON.stringify(e.data,this.replacer)),t}encodeAsBinary(e){const t=Xn(e),r=this.encodeAsString(t.packet),s=t.buffers;return s.unshift(r),s}}class je extends A{constructor(e){super(),this.opts=Object.assign({reviver:void 0,maxAttachments:10},typeof e=="function"?{reviver:e}:e)}add(e){let t;if(typeof e=="string"){if(this.reconstructor)throw new Error("got plaintext data when reconstructing a packet");t=this.decodeString(e);const r=t.type===m.BINARY_EVENT;r||t.type===m.BINARY_ACK?(t.type=r?m.EVENT:m.ACK,this.reconstructor=new er(t),t.attachments===0&&super.emitReserved("decoded",t)):super.emitReserved("decoded",t)}else if(Ve(e)||e.base64)if(this.reconstructor)t=this.reconstructor.takeBinaryData(e),t&&(this.reconstructor=null,super.emitReserved("decoded",t));else throw new Error("got binary data when not reconstructing a packet");else throw new Error("Unknown type: "+e)}decodeString(e){let t=0;const r={type:Number(e.charAt(0))};if(m[r.type]===void 0)throw new Error("unknown packet type "+r.type);if(r.type===m.BINARY_EVENT||r.type===m.BINARY_ACK){const i=t+1;for(;e.charAt(++t)!=="-"&&t!=e.length;);const o=e.substring(i,t);if(o!=Number(o)||e.charAt(t)!=="-")throw new Error("Illegal attachments");const c=Number(o);if(!tr(c)||c<0)throw new Error("Illegal attachments");if(c>this.opts.maxAttachments)throw new Error("too many attachments");r.attachments=c}if(e.charAt(t+1)==="/"){const i=t+1;for(;++t&&!(e.charAt(t)===","||t===e.length););r.nsp=e.substring(i,t)}else r.nsp="/";const s=e.charAt(t+1);if(s!==""&&Number(s)==s){const i=t+1;for(;++t;){const o=e.charAt(t);if(o==null||Number(o)!=o){--t;break}if(t===e.length)break}r.id=Number(e.substring(i,t+1))}if(e.charAt(++t)){const i=this.tryParse(e.substr(t));if(je.isPayloadValid(r.type,i))r.data=i;else throw new Error("invalid payload")}return r}tryParse(e){try{return JSON.parse(e,this.opts.reviver)}catch{return!1}}static isPayloadValid(e,t){switch(e){case m.CONNECT:return Ht(t);case m.DISCONNECT:return t===void 0;case m.CONNECT_ERROR:return typeof t=="string"||Ht(t);case m.EVENT:case m.BINARY_EVENT:return Array.isArray(t)&&(typeof t[0]=="number"||typeof t[0]=="string"&&Gn.indexOf(t[0])===-1);case m.ACK:case m.BINARY_ACK:return Array.isArray(t)}}destroy(){this.reconstructor&&(this.reconstructor.finishedReconstruction(),this.reconstructor=null)}}class er{constructor(e){this.packet=e,this.buffers=[],this.reconPack=e}takeBinaryData(e){if(this.buffers.push(e),this.buffers.length===this.reconPack.attachments){const t=Qn(this.reconPack,this.buffers);return this.finishedReconstruction(),t}return null}finishedReconstruction(){this.reconPack=null,this.buffers=[]}}const tr=Number.isInteger||function(n){return typeof n=="number"&&isFinite(n)&&Math.floor(n)===n};function Ht(n){return Object.prototype.toString.call(n)==="[object Object]"}const nr=Object.freeze(Object.defineProperty({__proto__:null,Decoder:je,Encoder:Zn,get PacketType(){return m}},Symbol.toStringTag,{value:"Module"}));function P(n,e,t){return n.on(e,t),function(){n.off(e,t)}}const rr=Object.freeze({connect:1,connect_error:1,disconnect:1,disconnecting:1,newListener:1,removeListener:1});class Ft extends A{constructor(e,t,r){super(),this.connected=!1,this.recovered=!1,this.receiveBuffer=[],this.sendBuffer=[],this._queue=[],this._queueSeq=0,this.ids=0,this.acks={},this.flags={},this.io=e,this.nsp=t,r&&r.auth&&(this.auth=r.auth),this._opts=Object.assign({},r),this.io._autoConnect&&this.open()}get disconnected(){return!this.connected}subEvents(){if(this.subs)return;const e=this.io;this.subs=[P(e,"open",this.onopen.bind(this)),P(e,"packet",this.onpacket.bind(this)),P(e,"error",this.onerror.bind(this)),P(e,"close",this.onclose.bind(this))]}get active(){return!!this.subs}connect(){return this.connected?this:(this.subEvents(),this.io._reconnecting||this.io.open(),this.io._readyState==="open"&&this.onopen(),this)}open(){return this.connect()}send(...e){return e.unshift("message"),this.emit.apply(this,e),this}emit(e,...t){var r,s,i;if(rr.hasOwnProperty(e))throw new Error('"'+e.toString()+'" is a reserved event name');if(t.unshift(e),this._opts.retries&&!this.flags.fromQueue&&!this.flags.volatile)return this._addToQueue(t),this;const o={type:m.EVENT,data:t};if(o.options={},o.options.compress=this.flags.compress!==!1,typeof t[t.length-1]=="function"){const d=this.ids++,_=t.pop();this._registerAckCallback(d,_),o.id=d}const c=(s=(r=this.io.engine)===null||r===void 0?void 0:r.transport)===null||s===void 0?void 0:s.writable,h=this.connected&&!(!((i=this.io.engine)===null||i===void 0)&&i._hasPingExpired());return this.flags.volatile&&!c||(h?(this.notifyOutgoingListeners(o),this.packet(o)):this.sendBuffer.push(o)),this.flags={},this}_registerAckCallback(e,t){var r;const s=(r=this.flags.timeout)!==null&&r!==void 0?r:this._opts.ackTimeout;if(s===void 0){this.acks[e]=t;return}const i=this.io.setTimeoutFn(()=>{delete this.acks[e];for(let c=0;c<this.sendBuffer.length;c++)this.sendBuffer[c].id===e&&this.sendBuffer.splice(c,1);t.call(this,new Error("operation has timed out"))},s),o=(...c)=>{this.io.clearTimeoutFn(i),t.apply(this,c)};o.withError=!0,this.acks[e]=o}emitWithAck(e,...t){return new Promise((r,s)=>{const i=(o,c)=>o?s(o):r(c);i.withError=!0,t.push(i),this.emit(e,...t)})}_addToQueue(e){let t;typeof e[e.length-1]=="function"&&(t=e.pop());const r={id:this._queueSeq++,tryCount:0,pending:!1,args:e,flags:Object.assign({fromQueue:!0},this.flags)};e.push((s,...i)=>(this._queue[0],s!==null?r.tryCount>this._opts.retries&&(this._queue.shift(),t&&t(s)):(this._queue.shift(),t&&t(null,...i)),r.pending=!1,this._drainQueue())),this._queue.push(r),this._drainQueue()}_drainQueue(e=!1){if(!this.connected||this._queue.length===0)return;const t=this._queue[0];t.pending&&!e||(t.pending=!0,t.tryCount++,this.flags=t.flags,this.emit.apply(this,t.args))}packet(e){e.nsp=this.nsp,this.io._packet(e)}onopen(){typeof this.auth=="function"?this.auth(e=>{this._sendConnectPacket(e)}):this._sendConnectPacket(this.auth)}_sendConnectPacket(e){this.packet({type:m.CONNECT,data:this._pid?Object.assign({pid:this._pid,offset:this._lastOffset},e):e})}onerror(e){this.connected||this.emitReserved("connect_error",e)}onclose(e,t){this.connected=!1,delete this.id,this.emitReserved("disconnect",e,t),this._clearAcks()}_clearAcks(){Object.keys(this.acks).forEach(e=>{if(!this.sendBuffer.some(r=>String(r.id)===e)){const r=this.acks[e];delete this.acks[e],r.withError&&r.call(this,new Error("socket has been disconnected"))}})}onpacket(e){if(e.nsp===this.nsp)switch(e.type){case m.CONNECT:e.data&&e.data.sid?this.onconnect(e.data.sid,e.data.pid):this.emitReserved("connect_error",new Error("It seems you are trying to reach a Socket.IO server in v2.x with a v3.x client, but they are not compatible (more information here: https://socket.io/docs/v3/migrating-from-2-x-to-3-0/)"));break;case m.EVENT:case m.BINARY_EVENT:this.onevent(e);break;case m.ACK:case m.BINARY_ACK:this.onack(e);break;case m.DISCONNECT:this.ondisconnect();break;case m.CONNECT_ERROR:this.destroy();const r=new Error(e.data.message);r.data=e.data.data,this.emitReserved("connect_error",r);break}}onevent(e){const t=e.data||[];e.id!=null&&t.push(this.ack(e.id)),this.connected?this.emitEvent(t):this.receiveBuffer.push(Object.freeze(t))}emitEvent(e){if(this._anyListeners&&this._anyListeners.length){const t=this._anyListeners.slice();for(const r of t)r.apply(this,e)}super.emit.apply(this,e),this._pid&&e.length&&typeof e[e.length-1]=="string"&&(this._lastOffset=e[e.length-1])}ack(e){const t=this;let r=!1;return function(...s){r||(r=!0,t.packet({type:m.ACK,id:e,data:s}))}}onack(e){const t=this.acks[e.id];typeof t=="function"&&(delete this.acks[e.id],t.withError&&e.data.unshift(null),t.apply(this,e.data))}onconnect(e,t){this.id=e,this.recovered=t&&this._pid===t,this._pid=t,this.connected=!0,this.emitBuffered(),this._drainQueue(!0),this.emitReserved("connect")}emitBuffered(){this.receiveBuffer.forEach(e=>this.emitEvent(e)),this.receiveBuffer=[],this.sendBuffer.forEach(e=>{this.notifyOutgoingListeners(e),this.packet(e)}),this.sendBuffer=[]}ondisconnect(){this.destroy(),this.onclose("io server disconnect")}destroy(){this.subs&&(this.subs.forEach(e=>e()),this.subs=void 0),this.io._destroy(this)}disconnect(){return this.connected&&this.packet({type:m.DISCONNECT}),this.destroy(),this.connected&&this.onclose("io client disconnect"),this}close(){return this.disconnect()}compress(e){return this.flags.compress=e,this}get volatile(){return this.flags.volatile=!0,this}timeout(e){return this.flags.timeout=e,this}onAny(e){return this._anyListeners=this._anyListeners||[],this._anyListeners.push(e),this}prependAny(e){return this._anyListeners=this._anyListeners||[],this._anyListeners.unshift(e),this}offAny(e){if(!this._anyListeners)return this;if(e){const t=this._anyListeners;for(let r=0;r<t.length;r++)if(e===t[r])return t.splice(r,1),this}else this._anyListeners=[];return this}listenersAny(){return this._anyListeners||[]}onAnyOutgoing(e){return this._anyOutgoingListeners=this._anyOutgoingListeners||[],this._anyOutgoingListeners.push(e),this}prependAnyOutgoing(e){return this._anyOutgoingListeners=this._anyOutgoingListeners||[],this._anyOutgoingListeners.unshift(e),this}offAnyOutgoing(e){if(!this._anyOutgoingListeners)return this;if(e){const t=this._anyOutgoingListeners;for(let r=0;r<t.length;r++)if(e===t[r])return t.splice(r,1),this}else this._anyOutgoingListeners=[];return this}listenersAnyOutgoing(){return this._anyOutgoingListeners||[]}notifyOutgoingListeners(e){if(this._anyOutgoingListeners&&this._anyOutgoingListeners.length){const t=this._anyOutgoingListeners.slice();for(const r of t)r.apply(this,e.data)}}}function X(n){n=n||{},this.ms=n.min||100,this.max=n.max||1e4,this.factor=n.factor||2,this.jitter=n.jitter>0&&n.jitter<=1?n.jitter:0,this.attempts=0}X.prototype.duration=function(){var n=this.ms*Math.pow(this.factor,this.attempts++);if(this.jitter){var e=Math.random(),t=Math.floor(e*this.jitter*n);n=(Math.floor(e*10)&1)==0?n-t:n+t}return Math.min(n,this.max)|0},X.prototype.reset=function(){this.attempts=0},X.prototype.setMin=function(n){this.ms=n},X.prototype.setMax=function(n){this.max=n},X.prototype.setJitter=function(n){this.jitter=n};class Ke extends A{constructor(e,t){var r;super(),this.nsps={},this.subs=[],e&&typeof e=="object"&&(t=e,e=void 0),t=t||{},t.path=t.path||"/socket.io",this.opts=t,ye(this,t),this.reconnection(t.reconnection!==!1),this.reconnectionAttempts(t.reconnectionAttempts||1/0),this.reconnectionDelay(t.reconnectionDelay||1e3),this.reconnectionDelayMax(t.reconnectionDelayMax||5e3),this.randomizationFactor((r=t.randomizationFactor)!==null&&r!==void 0?r:.5),this.backoff=new X({min:this.reconnectionDelay(),max:this.reconnectionDelayMax(),jitter:this.randomizationFactor()}),this.timeout(t.timeout==null?2e4:t.timeout),this._readyState="closed",this.uri=e;const s=t.parser||nr;this.encoder=new s.Encoder,this.decoder=new s.Decoder,this._autoConnect=t.autoConnect!==!1,this._autoConnect&&this.open()}reconnection(e){return arguments.length?(this._reconnection=!!e,e||(this.skipReconnect=!0),this):this._reconnection}reconnectionAttempts(e){return e===void 0?this._reconnectionAttempts:(this._reconnectionAttempts=e,this)}reconnectionDelay(e){var t;return e===void 0?this._reconnectionDelay:(this._reconnectionDelay=e,(t=this.backoff)===null||t===void 0||t.setMin(e),this)}randomizationFactor(e){var t;return e===void 0?this._randomizationFactor:(this._randomizationFactor=e,(t=this.backoff)===null||t===void 0||t.setJitter(e),this)}reconnectionDelayMax(e){var t;return e===void 0?this._reconnectionDelayMax:(this._reconnectionDelayMax=e,(t=this.backoff)===null||t===void 0||t.setMax(e),this)}timeout(e){return arguments.length?(this._timeout=e,this):this._timeout}maybeReconnectOnOpen(){!this._reconnecting&&this._reconnection&&this.backoff.attempts===0&&this.reconnect()}open(e){if(~this._readyState.indexOf("open"))return this;this.engine=new Vn(this.uri,this.opts);const t=this.engine,r=this;this._readyState="opening",this.skipReconnect=!1;const s=P(t,"open",function(){r.onopen(),e&&e()}),i=c=>{this.cleanup(),this._readyState="closed",this.emitReserved("error",c),e?e(c):this.maybeReconnectOnOpen()},o=P(t,"error",i);if(this._timeout!==!1){const c=this._timeout,h=this.setTimeoutFn(()=>{s(),i(new Error("timeout")),t.close()},c);this.opts.autoUnref&&h.unref(),this.subs.push(()=>{this.clearTimeoutFn(h)})}return this.subs.push(s),this.subs.push(o),this}connect(e){return this.open(e)}onopen(){this.cleanup(),this._readyState="open",this.emitReserved("open");const e=this.engine;this.subs.push(P(e,"ping",this.onping.bind(this)),P(e,"data",this.ondata.bind(this)),P(e,"error",this.onerror.bind(this)),P(e,"close",this.onclose.bind(this)),P(this.decoder,"decoded",this.ondecoded.bind(this)))}onping(){this.emitReserved("ping")}ondata(e){try{this.decoder.add(e)}catch(t){this.onclose("parse error",t)}}ondecoded(e){be(()=>{this.emitReserved("packet",e)},this.setTimeoutFn)}onerror(e){this.emitReserved("error",e)}socket(e,t){let r=this.nsps[e];return r?this._autoConnect&&!r.active&&r.connect():(r=new Ft(this,e,t),this.nsps[e]=r),r}_destroy(e){const t=Object.keys(this.nsps);for(const r of t)if(this.nsps[r].active)return;this._close()}_packet(e){const t=this.encoder.encode(e);for(let r=0;r<t.length;r++)this.engine.write(t[r],e.options)}cleanup(){this.subs.forEach(e=>e()),this.subs.length=0,this.decoder.destroy()}_close(){this.skipReconnect=!0,this._reconnecting=!1,this.onclose("forced close")}disconnect(){return this._close()}onclose(e,t){var r;this.cleanup(),(r=this.engine)===null||r===void 0||r.close(),this.backoff.reset(),this._readyState="closed",this.emitReserved("close",e,t),this._reconnection&&!this.skipReconnect&&this.reconnect()}reconnect(){if(this._reconnecting||this.skipReconnect)return this;const e=this;if(this.backoff.attempts>=this._reconnectionAttempts)this.backoff.reset(),this.emitReserved("reconnect_failed"),this._reconnecting=!1;else{const t=this.backoff.duration();this._reconnecting=!0;const r=this.setTimeoutFn(()=>{e.skipReconnect||(this.emitReserved("reconnect_attempt",e.backoff.attempts),!e.skipReconnect&&e.open(s=>{s?(e._reconnecting=!1,e.reconnect(),this.emitReserved("reconnect_error",s)):e.onreconnect()}))},t);this.opts.autoUnref&&r.unref(),this.subs.push(()=>{this.clearTimeoutFn(r)})}}onreconnect(){const e=this.backoff.attempts;this._reconnecting=!1,this.backoff.reset(),this.emitReserved("reconnect",e)}}const te={};function xe(n,e){typeof n=="object"&&(e=n,n=void 0),e=e||{};const t=Wn(n,e.path||"/socket.io"),r=t.source,s=t.id,i=t.path,o=te[s]&&i in te[s].nsps,c=e.forceNew||e["force new connection"]||e.multiplex===!1||o;let h;return c?h=new Ke(r,e):(te[s]||(te[s]=new Ke(r,e)),h=te[s]),t.query&&!e.query&&(e.query=t.queryKey),h.socket(t.path,e)}Object.assign(xe,{Manager:Ke,Socket:Ft,io:xe,connect:xe});class zt{constructor(e,t,r,s,i){this.orgId=t,this.onEvent=s,this.onOpen=i,this.closed=!1,this.streamingBuffer="",this.conversationId=r,this.socket=xe(`${e}/chat`,{auth:o=>o({org_id:this.orgId,conversation_id:this.conversationId??void 0}),transports:["websocket","polling"]}),this.socket.on("connect",()=>{this.socket.emit("join")}),this.socket.on("connected",o=>{var c;this.conversationId=o.conversation_id,(c=this.onOpen)==null||c.call(this,o.conversation_id)}),this.socket.on("response_token",o=>{this.streamingBuffer+=o.token,this.onEvent({v:1,type:"message.delta",body:o.token})}),this.socket.on("response_complete",()=>{const o=this.streamingBuffer;this.streamingBuffer="",this.onEvent({v:1,type:"message",direction:"inbound",sender:"ai",body:o,messageId:`ai-${Date.now()}`,ts:new Date().toISOString()})}),this.socket.on("staff_message",o=>{this.onEvent({v:1,type:"message",direction:"outbound",sender:"staff",body:o.content,messageId:`staff-${Date.now()}`,ts:new Date().toISOString()})}),this.socket.on("takeover_event",()=>{this.onEvent({v:1,type:"message",direction:"inbound",sender:"system",body:"",messageId:`takeover-${Date.now()}`,ts:new Date().toISOString()})})}send(e){if(this.closed)return;const t=e.message;typeof t=="string"&&t.length>0&&this.socket.emit("send_message",{message:t})}close(){this.closed=!0,this.socket.disconnect()}}const sr="http://localhost:8000";async function ir(n,e=sr){const t=await fetch(`${e}/api/public/webchat/${n}/config`);if(!t.ok)throw new Error(`Config fetch failed: ${t.status}`);return t.json()}async function or(n,e){n.send({message:e})}async function ar(n,e,t){}async function cr(n,e,t,r){}async function lr(n,e,t){const r=await fetch(`${n}/api/public/webchat/${e}/conversations/${t}/messages`);return r.ok?(await r.json()).messages??[]:[]}function hr(n){return n.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}function Q(n){return n=hr(n),n=n.replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>"),n=n.replace(/\*(.+?)\*/g,"<em>$1</em>"),n=n.replace(/`(.+?)`/g,"<code>$1</code>"),n=n.replace(/(\bhttps?:\/\/[^\s<"]+)/g,e=>`<a href="${e}" target="_blank" rel="noopener noreferrer">${e}</a>`),n}function Vt(n){if(!n)return"";const e=n.split(`
`),t=[];let r=!1,s=!1;const i=()=>{r&&(t.push("</ul>"),r=!1),s&&(t.push("</ol>"),s=!1)};for(const o of e){let c;if(c=o.match(/^### (.+)/)){i(),t.push(`<h4>${Q(c[1])}</h4>`);continue}if(c=o.match(/^## (.+)/)){i(),t.push(`<h3>${Q(c[1])}</h3>`);continue}if(c=o.match(/^# (.+)/)){i(),t.push(`<h2>${Q(c[1])}</h2>`);continue}if(/^---+$/.test(o.trim())){i(),t.push("<hr>");continue}if(c=o.match(/^[-•→*] (.+)/)){s&&(t.push("</ol>"),s=!1),r||(t.push("<ul>"),r=!0),t.push(`<li>${Q(c[1])}</li>`);continue}if(c=o.match(/^\d+\. (.+)/)){r&&(t.push("</ul>"),r=!1),s||(t.push("<ol>"),s=!0),t.push(`<li>${Q(c[1])}</li>`);continue}if(o.trim()===""){i(),t.push('<div style="height:6px"></div>');continue}i(),t.push(`<p class="md-p">${Q(o)}</p>`)}return i(),t.join("")}function ur({orgId:n,apiBase:e,initialConfig:t}){const r=`cw_consent:${n}`,[s,i]=L(!1),[o,c]=L("welcome"),[h,l]=L("en"),[d,_]=L([]),[a,p]=L(""),[v,C]=L(!1),[E,w]=L(!1),[b,O]=L(()=>typeof localStorage<"u"&&localStorage.getItem(r)==="1"),N=fe(null),k=fe(null),B=fe(null);vt(()=>{const f=ln(n);return f&&lr(e,n,f).then(g=>{g.length>0&&(_(g.map(x=>({id:x.id,direction:x.direction,body:x.body??"",ts:String(x.createdAt??new Date().toISOString()),html:x.direction==="inbound"?Vt(x.body??""):void 0}))),c("chat"))}).catch(()=>{}),N.current=new zt(e,n,f,V,g=>Et(n,g)),()=>{var g;(g=N.current)==null||g.close()}},[n,e]);function V(f){if(f.type==="typing"){C(!0),k.current&&clearTimeout(k.current),k.current=setTimeout(()=>C(!1),15e3);return}if(f.type==="message.delta"&&f.body!==void 0){if(k.current&&(clearTimeout(k.current),k.current=null),C(!1),B.current===null){B.current="__streaming__";const g={id:"__streaming__",direction:"inbound",body:f.body,ts:f.ts??new Date().toISOString(),sender:"ai",streaming:!0};_(x=>[...x,g])}else _(g=>g.map(x=>x.id==="__streaming__"?{...x,body:x.body+f.body}:x));return}if(f.type==="message.delta.abort"){B.current!==null&&(_(g=>g.filter(x=>x.id!=="__streaming__")),B.current=null);return}f.type==="message"&&f.body!==void 0&&(k.current&&(clearTimeout(k.current),k.current=null),C(!1),_(g=>{if(f.messageId&&g.some(H=>H.id===f.messageId))return g;const x=f.direction==="outbound"&&f.sender==="staff",Y=x?{id:f.messageId??`ws-${Date.now()}`,direction:"inbound",body:f.body??"",ts:f.ts??new Date().toISOString(),sender:"staff",html:f.body??"",interactive:f.interactive}:{id:f.messageId??`ws-${Date.now()}`,direction:"inbound",body:f.body??"",ts:f.ts??new Date().toISOString(),sender:f.sender??"ai",html:Vt(f.body??""),interactive:f.interactive};if(B.current!==null)return B.current=null,g.map(H=>H.id==="__streaming__"?Y:H);if(f.direction==="outbound"&&(f.sender==="visitor"||!f.sender))return g;if(x){if(!g.some(K=>K.sender==="staff")){const K={id:`system-staff-${Date.now()}`,direction:"inbound",body:"",ts:f.ts??new Date().toISOString(),sender:"system"};return[...g,K,Y]}return[...g,Y]}return[...g,Y]}))}async function q(f){const g=(f??a).trim();if(!g||E||!N.current)return;const x=`opt-${Date.now()}`,Y={id:x,direction:"outbound",body:g,ts:new Date().toISOString(),optimistic:!0};_(H=>[...H,Y]),p(""),w(!0),C(!0),await or(N.current,g),_(H=>H.map(K=>K.id===x?{...K,optimistic:!1}:K)),w(!1)}function W(f){var x;l(f),ar();const g=t.preChatFormEnabled&&((x=t.preChatFields)==null?void 0:x.some(Y=>Y.field==="email"));c(g?"prechat":"chat")}async function R(f,g){await cr(),c("chat")}function U(){typeof localStorage<"u"&&localStorage.setItem(r,"1"),O(!0)}function Je(f){p(f)}function ke(){var f;hn(n),(f=N.current)==null||f.close(),k.current&&(clearTimeout(k.current),k.current=null),B.current=null,_([]),C(!1),w(!1),p(""),c("welcome"),N.current=new zt(e,n,null,V,g=>Et(n,g))}return u(j,{children:[s&&u(cn,{config:t,phase:o,lang:h,messages:d,isTyping:v,inputValue:a,isSending:E,consentAccepted:b,onLangSelect:W,onPreChatSubmit:R,onAcceptConsent:U,onInputChange:p,onSend:q,onClose:()=>i(!1),onReset:ke,onSuggestion:Je,onSlotSelect:q}),u(rn,{config:t,isOpen:s,onClick:()=>i(f=>!f)})]})}const fr=`
:host {
  all: initial;
  font-family: var(--cw-font, 'Poppins'), sans-serif;
  font-size: 14px;
  color: #1f2937;
  box-sizing: border-box;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

/* ── CSS tokens ──────────────────────────────────────────────────────────── */
:host {
  --cp:   var(--cw-primary,   #00D9FF);
  --cs:   var(--cw-secondary, #4D27D2);
  --cbg:  var(--cw-surface,   #ffffff);
  --ct:   var(--cw-text,      #1f2937);
  --ctl:  var(--cw-text-light,#6b7280);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --ease-out:    cubic-bezier(0.4, 0, 0.2, 1);
}

/* ══════════════════════════════════════
   LAUNCHER
══════════════════════════════════════ */
.launcher {
  position: fixed;
  bottom: 24px;
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--cp) 0%, var(--cs) 100%);
  color: white;
  border: none;
  cursor: pointer;
  z-index: 2147483647;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6px 24px rgba(0,0,0,0.22);
  transition: transform 0.3s var(--ease-spring), box-shadow 0.25s var(--ease-out);
}
.launcher::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: inherit;
  opacity: 0.45;
  animation: cwPulse 2.4s ease-out infinite;
}
@keyframes cwPulse {
  0%   { transform: scale(1);   opacity: 0.45; }
  70%  { transform: scale(1.7); opacity: 0;    }
  100% { transform: scale(1.7); opacity: 0;    }
}
.launcher:hover {
  transform: scale(1.1);
  box-shadow: 0 10px 32px rgba(0,0,0,0.28);
}
.launcher.pos-right { right: 24px; }
.launcher.pos-left  { left:  24px; }
.launcher svg { width: 26px; height: 26px; position: relative; }

/* ══════════════════════════════════════
   CHAT WINDOW
══════════════════════════════════════ */
.chat-window {
  position: fixed;
  bottom: 100px;
  z-index: 2147483646;
  width: 360px;
  height: 540px;
  background: var(--cbg);
  border-radius: 20px;
  box-shadow:
    0 24px 64px rgba(0,0,0,0.14),
    0 6px 20px rgba(0,0,0,0.08),
    0 0 0 1px rgba(0,0,0,0.05);
  overflow: hidden;
  display: none;
  flex-direction: column;
  opacity: 0;
  transform: translateY(20px) scale(0.94);
  transition: opacity 0.28s var(--ease-out), transform 0.32s var(--ease-spring);
}
.chat-window.pos-right { right: 24px; }
.chat-window.pos-left  { left:  24px; }
.chat-window.open {
  display: flex;
  opacity: 1;
  transform: translateY(0) scale(1);
}

/* ══════════════════════════════════════
   HEADER
══════════════════════════════════════ */
.header {
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 11px;
  background: linear-gradient(135deg, var(--cs) 0%, var(--cp) 100%);
  flex-shrink: 0;
  position: relative;
}
.header::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E");
  pointer-events: none;
}
.header-avatar {
  width: 38px; height: 38px;
  border-radius: 50%;
  background: rgba(255,255,255,0.18);
  border: 1.5px solid rgba(255,255,255,0.3);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; position: relative; overflow: hidden;
}
.header-avatar img {
  width: 100%; height: 100%;
  object-fit: contain; border-radius: 50%;
}
.header-info { flex: 1; position: relative; }
.header-title { font-size: 14px; font-weight: 600; color: #fff; display: block; line-height: 1.2; }
.header-status { display: flex; align-items: center; gap: 5px; margin-top: 3px; }
.status-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: #4ade80; box-shadow: 0 0 0 2px rgba(74,222,128,0.3);
  animation: cwStatusPulse 2s ease-in-out infinite;
}
@keyframes cwStatusPulse {
  0%,100% { box-shadow: 0 0 0 2px rgba(74,222,128,0.3); }
  50%      { box-shadow: 0 0 0 4px rgba(74,222,128,0.15); }
}
.header-status span { font-size: 11px; color: rgba(255,255,255,0.75); }
.close-btn {
  position: relative;
  background: rgba(255,255,255,0.16);
  border: 1.5px solid rgba(255,255,255,0.25);
  color: white; cursor: pointer; border-radius: 50%;
  width: 30px; height: 30px;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.2s ease, transform 0.2s ease;
  font-size: 18px; flex-shrink: 0; line-height: 1;
}
.close-btn:hover { background: rgba(255,255,255,0.28); transform: rotate(90deg) scale(1.05); }
.reset-btn {
  position: relative;
  background: rgba(255,255,255,0.16);
  border: 1.5px solid rgba(255,255,255,0.25);
  color: white; cursor: pointer; border-radius: 50%;
  width: 30px; height: 30px; margin-right: 8px;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.2s ease, transform 0.2s ease;
  flex-shrink: 0; line-height: 1;
}
.reset-btn:hover { background: rgba(255,255,255,0.28); transform: rotate(-30deg) scale(1.05); }

/* ══════════════════════════════════════
   WELCOME SCREEN
══════════════════════════════════════ */
.welcome {
  flex: 1;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  padding: 36px 28px 28px;
  text-align: center;
  background: var(--cbg);
}
.welcome-icon {
  width: 68px; height: 68px; border-radius: 50%;
  background: linear-gradient(135deg, rgba(0,217,255,0.12) 0%, rgba(77,39,210,0.08) 100%);
  border: 2px solid rgba(0,217,255,0.2);
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 20px;
}
.welcome-icon svg { width: 28px; height: 28px; stroke: var(--cp); }
.welcome-title { font-size: 19px; font-weight: 700; color: var(--ct); margin-bottom: 8px; line-height: 1.3; }
.welcome-sub { font-size: 13px; color: var(--ctl); line-height: 1.6; margin-bottom: 28px; max-width: 260px; }

/* Language picker */
.lang-picker {
  display: inline-flex; background: #f0f1f3;
  border-radius: 999px; padding: 3px; gap: 2px;
}
.lang-btn {
  padding: 7px 18px; background: transparent; border: none;
  border-radius: 999px; cursor: pointer; font-size: 12px; font-weight: 600;
  font-family: inherit; color: var(--ctl); letter-spacing: 0.5px;
  transition: color 0.18s ease, background 0.18s ease;
}
.lang-btn:hover { color: var(--ct); }
.lang-btn.selected { background: #fff; color: var(--ct); box-shadow: 0 1px 4px rgba(0,0,0,0.12); }

/* ══════════════════════════════════════
   CHAT BODY
══════════════════════════════════════ */
.chat-body { display: none; flex-direction: column; flex: 1; overflow: hidden; }
.chat-body.active { display: flex; }

.messages {
  flex: 1; overflow-y: auto;
  padding: 18px 14px;
  background: #f5f6f8;
  display: flex; flex-direction: column;
  gap: 8px; scroll-behavior: smooth;
}
.messages::-webkit-scrollbar { width: 4px; }
.messages::-webkit-scrollbar-track { background: transparent; }
.messages::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.12); border-radius: 4px; }

/* Bubbles */
.bubble {
  padding: 10px 14px;
  max-width: 82%;
  word-wrap: break-word;
  font-size: 13.5px;
  line-height: 1.55;
  white-space: pre-line;
  animation: cwBubbleIn 0.22s var(--ease-out);
}
@keyframes cwBubbleIn {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
.bubble.user {
  background: linear-gradient(135deg, var(--cp) 0%, var(--cs) 100%);
  color: white; align-self: flex-end;
  border-radius: 18px 18px 4px 18px;
  box-shadow: 0 3px 10px rgba(0,0,0,0.14);
}
.bubble.bot {
  background: #ffffff; color: var(--ct); align-self: flex-start;
  border-radius: 18px 18px 18px 4px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.07);
  border: 1px solid rgba(0,0,0,0.06);
}
.bubble.optimistic { opacity: 0.65; }

/* Streaming cursor — blinks at the end of the in-progress answer bubble */
.streaming-cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  background: var(--cp);
  border-radius: 1px;
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: cwCaret 0.9s step-end infinite;
}
@keyframes cwCaret {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0; }
}

/* Typing indicator */
.typing-indicator {
  display: flex; align-items: center; gap: 5px;
  padding: 12px 15px; background: #ffffff;
  border-radius: 18px 18px 18px 4px;
  max-width: 68px; align-self: flex-start;
  box-shadow: 0 2px 8px rgba(0,0,0,0.07);
  border: 1px solid rgba(0,0,0,0.06);
  animation: cwBubbleIn 0.22s var(--ease-out);
}
.typing-dot {
  width: 7px; height: 7px; background: var(--cp);
  border-radius: 50%; opacity: 0.6;
  animation: cwTyping 1.3s ease-in-out infinite;
}
.typing-dot:nth-child(1) { animation-delay: 0s; }
.typing-dot:nth-child(2) { animation-delay: 0.18s; }
.typing-dot:nth-child(3) { animation-delay: 0.36s; }
@keyframes cwTyping {
  0%,60%,100% { transform: translateY(0); opacity: 0.5; }
  30%          { transform: translateY(-5px); opacity: 1; }
}

/* Suggested questions */
.suggestions { display: flex; flex-direction: column; gap: 6px; margin: 4px 0; align-self: flex-start; max-width: 88%; }
.suggestion-btn {
  background: #fff; border: 1.5px solid rgba(0,0,0,0.1); border-radius: 12px;
  padding: 9px 13px; text-align: left; font-size: 13px; color: var(--ct);
  cursor: pointer; font-family: inherit; line-height: 1.4;
  transition: border-color 0.2s ease, transform 0.15s ease, background 0.2s ease;
  animation: cwBubbleIn 0.22s var(--ease-out);
}
.suggestion-btn:hover { border-color: var(--cp); background: rgba(0,217,255,0.05); transform: translateX(3px); }

/* Bot bubble markdown */
.bubble.bot h2 { font-size: 13.5px; font-weight: 700; margin: 8px 0 3px; }
.bubble.bot h3 { font-size: 13px; font-weight: 700; margin: 6px 0 2px; }
.bubble.bot h4 { font-size: 12.5px; font-weight: 600; margin: 5px 0 2px; color: var(--ctl); text-transform: uppercase; letter-spacing: 0.4px; }
.bubble.bot ul { list-style: none; padding: 0; margin: 4px 0; }
.bubble.bot ul li::before { content: '→ '; color: var(--cp); font-weight: 600; }
.bubble.bot ol { padding-left: 18px; margin: 4px 0; }
.bubble.bot li { margin: 3px 0; line-height: 1.5; }
.bubble.bot strong { font-weight: 700; }
.bubble.bot em { font-style: italic; color: var(--ctl); }
.bubble.bot code { background: #f0f1f3; padding: 1px 5px; border-radius: 4px; font-family: monospace; font-size: 12px; }
.bubble.bot hr { border: none; border-top: 1px solid rgba(0,0,0,0.08); margin: 7px 0; }
.bubble.bot .md-p { margin: 3px 0; line-height: 1.55; }
.bubble.bot a { color: var(--cp); text-decoration: underline; word-break: break-all; }

/* ══════════════════════════════════════
   INPUT
══════════════════════════════════════ */
.controls {
  padding: 11px 12px; background: var(--cbg);
  border-top: 1px solid rgba(0,0,0,0.07);
  display: flex; align-items: flex-end; gap: 9px;
}
.textarea {
  flex: 1; padding: 10px 13px;
  border: 1.5px solid rgba(0,0,0,0.1); border-radius: 12px;
  background: #f5f6f8; color: var(--ct);
  resize: none; font-family: inherit; font-size: 13.5px;
  line-height: 1.5; max-height: 110px; min-height: 42px;
  outline: none; transition: border-color 0.2s ease, background 0.2s ease;
}
.textarea:focus { border-color: var(--cp); background: #fff; }
.textarea::placeholder { color: #bbb; }
.send-btn {
  width: 42px; height: 42px; border-radius: 12px;
  background: linear-gradient(135deg, var(--cp) 0%, var(--cs) 100%);
  color: white; border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  box-shadow: 0 3px 10px rgba(0,0,0,0.18);
  transition: transform 0.2s var(--ease-spring), box-shadow 0.2s ease;
}
.send-btn:hover { transform: scale(1.08); box-shadow: 0 5px 16px rgba(0,0,0,0.22); }
.send-btn:disabled { opacity: 0.4; cursor: default; transform: none; }
.send-btn svg { width: 19px; height: 19px; }

/* Staff bubble */
.bubble.staff {
  background: #fff8e1;
  border: 1px solid rgba(245,158,11,0.25);
}
.staff-label {
  display: block; font-size: 10px; font-weight: 700;
  color: #b45309; letter-spacing: 0.5px; text-transform: uppercase;
  margin-bottom: 4px;
}

/* System notice */
.system-notice {
  align-self: center;
  background: rgba(0,0,0,0.05);
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 11px;
  color: var(--ctl);
  text-align: center;
  animation: cwBubbleIn 0.22s var(--ease-out);
}

/* Pre-chat form */
.prechat-form {
  width: 100%; display: flex; flex-direction: column; gap: 10px; margin-top: 4px;
}
.prechat-input {
  width: 100%; padding: 10px 13px;
  border: 1.5px solid rgba(0,0,0,0.12); border-radius: 10px;
  font-size: 13.5px; font-family: inherit; color: var(--ct);
  background: #f5f6f8; outline: none;
  transition: border-color 0.2s ease, background 0.2s ease;
}
.prechat-input:focus { border-color: var(--cp); background: #fff; }
.prechat-input::placeholder { color: #bbb; }
.prechat-error { font-size: 12px; color: #ef4444; margin: -4px 0; }
.prechat-submit {
  padding: 11px; border-radius: 10px;
  background: linear-gradient(135deg, var(--cp) 0%, var(--cs) 100%);
  color: white; border: none; font-size: 13.5px; font-weight: 600;
  font-family: inherit; cursor: pointer;
  transition: opacity 0.2s ease;
}
.prechat-submit:disabled { opacity: 0.5; cursor: default; }
.prechat-skip {
  background: none; border: none; font-size: 12px; color: var(--ctl);
  cursor: pointer; font-family: inherit; text-decoration: underline;
  padding: 2px 0; align-self: center;
}

/* AI Act Art. 50 disclosure — welcome screen inline notice */
.ai-notice {
  font-size: 11.5px; color: var(--ctl);
  background: #f0f9ff; border: 1px solid rgba(0,153,255,0.18);
  border-radius: 8px; padding: 6px 10px;
  text-align: center; margin: 4px 0;
  line-height: 1.45;
}

/* AI Act Art. 50 disclosure — persistent strip at top of chat body */
.ai-notice-strip {
  font-size: 11px; color: var(--ctl);
  background: #f0f9ff; border-bottom: 1px solid rgba(0,153,255,0.15);
  padding: 5px 12px; text-align: center; flex-shrink: 0;
}

/* Consent banner */
.consent-banner {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  padding: 8px 12px;
  background: #fffbeb;
  border-top: 1px solid rgba(245,158,11,0.25);
  font-size: 11.5px; color: var(--ctl);
}
.consent-accept {
  flex-shrink: 0;
  padding: 4px 12px; border-radius: 6px;
  background: linear-gradient(135deg, var(--cp) 0%, var(--cs) 100%);
  color: white; border: none; font-size: 11.5px; font-weight: 600;
  font-family: inherit; cursor: pointer;
}

/* ══════════════════════════════════════
   FOOTER
══════════════════════════════════════ */
.footer {
  padding: 7px 12px; text-align: center;
  background: var(--cbg); border-top: 1px solid rgba(0,0,0,0.05);
}
.footer a {
  font-size: 11px; color: var(--ctl); text-decoration: none;
  opacity: 0.65; transition: opacity 0.2s; font-family: inherit;
}
.footer a:hover { opacity: 1; }
`;if(!window.__platformWidgetLoaded){window.__platformWidgetLoaded=!0;const n=document.currentScript??document.querySelector("script[data-org-id]"),e=(n==null?void 0:n.dataset.orgId)??"",t=(n==null?void 0:n.dataset.apiBase)??"http://localhost:8000";e?ir(e,t).then(r=>{const s=document.createElement("div");s.id="platform-widget-root",s.style.cssText="position:fixed;z-index:2147483647;top:0;left:0;width:0;height:0;overflow:visible;pointer-events:none",document.body.appendChild(s);const i=s.attachShadow({mode:"open"}),o=document.createElement("style");o.textContent=fr,i.appendChild(o);const c=document.createElement("div");c.style.cssText="pointer-events:auto",c.style.setProperty("--cw-primary",r.primaryColor),c.style.setProperty("--cw-secondary",r.secondaryColor??dr(r.primaryColor,.4)),i.appendChild(c),Qt(tt(ur,{orgId:e,apiBase:t,initialConfig:r}),c)}).catch(()=>{}):console.warn("[GenAI Widget] Missing data-org-id attribute on <script> tag.")}function dr(n,e){const t=n.replace("#",""),r=t.length===3?t.split("").map(h=>h+h).join(""):t,s=parseInt(r,16),i=Math.max(0,(s>>16&255)*(1-e)),o=Math.max(0,(s>>8&255)*(1-e)),c=Math.max(0,(s&255)*(1-e));return`#${[i,o,c].map(h=>Math.round(h).toString(16).padStart(2,"0")).join("")}`}})();
