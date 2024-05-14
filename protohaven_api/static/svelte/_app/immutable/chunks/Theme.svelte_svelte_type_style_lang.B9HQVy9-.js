import{s as L,e as J,i as j,d as g,b as S,h as y,j as V,M as U,G as Y,c as T,k as I,m as P,n as D,p as v,y as X,u as z,g as A,a as O,ac as p,t as Z,v as x,x as ee,A as K,w as fe,q as ae}from"./scheduler.DcN7B0mK.js";import{S as F,i as R,g as Q,a as N,c as W,t as C}from"./index.D46FeKIJ.js";import{w as ce}from"./index.Brx0Z4nw.js";function We(t){return(t==null?void 0:t.length)!==void 0?t:Array.from(t)}function M(t,e){const l={},i={},o={$$scope:1};let a=t.length;for(;a--;){const f=t[a],u=e[a];if(u){for(const s in f)s in u||(i[s]=1);for(const s in u)o[s]||(l[s]=u[s],o[s]=1);t[a]=u}else for(const s in f)o[s]=1}for(const f in i)f in l||(l[f]=void 0);return l}function Ye(t){return typeof t=="object"&&t!==null?t:{}}function le(){return window.location.href.indexOf("localhost")===-1?"https://api.protohaven.org":"http://localhost:5000"}function Ze(t,e){return fetch(le()+t,{method:"POST",headers:{Accept:"application/json","Content-Type":"application/json"},body:JSON.stringify(e)}).then(l=>l.text()).then(l=>{try{return JSON.parse(l)}catch{throw Error(`Invalid reply from server: ${l}`)}})}function xe(t){return fetch(le()+t).then(e=>e.text()).then(e=>{try{return JSON.parse(e)}catch{throw Error(`Invalid reply from server: ${e}`)}})}function we(){const t=window?window.getComputedStyle(document.body,null):{};return parseInt(t&&t.getPropertyValue("padding-right")||0,10)}function re(){let t=document.createElement("div");t.style.position="absolute",t.style.top="-9999px",t.style.width="50px",t.style.height="50px",t.style.overflow="scroll",document.body.appendChild(t);const e=t.offsetWidth-t.clientWidth;return document.body.removeChild(t),e}function de(t){document.body.style.paddingRight=t>0?`${t}px`:null}function he(){return window?document.body.clientWidth<window.innerWidth:!1}function me(t){const e=typeof t;return t!==null&&(e==="object"||e==="function")}function pe(){const t=re(),e=document.querySelectorAll(".fixed-top, .fixed-bottom, .is-fixed, .sticky-top")[0],l=e?parseInt(e.style.paddingRight||0,10):0;he()&&de(l+t)}function $(t,e,l){return l===!0||l===""?t?"col":`col-${e}`:l==="auto"?t?"col-auto":`col-${e}-auto`:t?`col-${l}`:`col-${e}-${l}`}function $e(t,...e){return t.addEventListener(...e),()=>t.removeEventListener(...e)}function te(t){let e="";if(typeof t=="string"||typeof t=="number")e+=t;else if(typeof t=="object")if(Array.isArray(t))e=t.map(te).filter(Boolean).join(" ");else for(let l in t)t[l]&&(e&&(e+=" "),e+=l);return e}const q=(...t)=>t.map(te).filter(Boolean).join(" ");function el(t){if(!t)return 0;let{transitionDuration:e,transitionDelay:l}=window.getComputedStyle(t);const i=Number.parseFloat(e),o=Number.parseFloat(l);return!i&&!o?0:(e=e.split(",")[0],l=l.split(",")[0],(Number.parseFloat(e)+Number.parseFloat(l))*1e3)}function ll(){return"xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g,t=>{const e=Math.random()*16|0;return(t==="x"?e:e&3|8).toString(16)})}function be(t){let e,l,i,o,a;const f=t[17].default,u=T(f,t,t[16],null),s=u||ye(t);let n=[t[8],{class:t[6]},{disabled:t[2]},{value:t[4]},{"aria-label":l=t[7]||t[5]}],c={};for(let d=0;d<n.length;d+=1)c=y(c,n[d]);return{c(){e=I("button"),s&&s.c(),this.h()},l(d){e=P(d,"BUTTON",{class:!0,"aria-label":!0});var r=D(e);s&&s.l(r),r.forEach(g),this.h()},h(){v(e,c)},m(d,r){j(d,e,r),s&&s.m(e,null),e.autofocus&&e.focus(),t[21](e),i=!0,o||(a=X(e,"click",t[19]),o=!0)},p(d,r){u?u.p&&(!i||r&65536)&&z(u,f,d,d[16],i?O(f,d[16],r,null):A(d[16]),null):s&&s.p&&(!i||r&65538)&&s.p(d,i?r:-1),v(e,c=M(n,[r&256&&d[8],(!i||r&64)&&{class:d[6]},(!i||r&4)&&{disabled:d[2]},(!i||r&16)&&{value:d[4]},(!i||r&160&&l!==(l=d[7]||d[5]))&&{"aria-label":l}]))},i(d){i||(C(s,d),i=!0)},o(d){N(s,d),i=!1},d(d){d&&g(e),s&&s.d(d),t[21](null),o=!1,a()}}}function _e(t){let e,l,i,o,a,f,u;const s=[Ne,ve],n=[];function c(b,h){return b[1]?0:1}l=c(t),i=n[l]=s[l](t);let d=[t[8],{class:t[6]},{href:t[3]},{"aria-label":o=t[7]||t[5]}],r={};for(let b=0;b<d.length;b+=1)r=y(r,d[b]);return{c(){e=I("a"),i.c(),this.h()},l(b){e=P(b,"A",{class:!0,href:!0,"aria-label":!0});var h=D(e);i.l(h),h.forEach(g),this.h()},h(){v(e,r),p(e,"disabled",t[2])},m(b,h){j(b,e,h),n[l].m(e,null),t[20](e),a=!0,f||(u=X(e,"click",t[18]),f=!0)},p(b,h){let _=l;l=c(b),l===_?n[l].p(b,h):(Q(),N(n[_],1,1,()=>{n[_]=null}),W(),i=n[l],i?i.p(b,h):(i=n[l]=s[l](b),i.c()),C(i,1),i.m(e,null)),v(e,r=M(d,[h&256&&b[8],(!a||h&64)&&{class:b[6]},(!a||h&8)&&{href:b[3]},(!a||h&160&&o!==(o=b[7]||b[5]))&&{"aria-label":o}])),p(e,"disabled",b[2])},i(b){a||(C(i),a=!0)},o(b){N(i),a=!1},d(b){b&&g(e),n[l].d(),t[20](null),f=!1,u()}}}function ge(t){let e;const l=t[17].default,i=T(l,t,t[16],null);return{c(){i&&i.c()},l(o){i&&i.l(o)},m(o,a){i&&i.m(o,a),e=!0},p(o,a){i&&i.p&&(!e||a&65536)&&z(i,l,o,o[16],e?O(l,o[16],a,null):A(o[16]),null)},i(o){e||(C(i,o),e=!0)},o(o){N(i,o),e=!1},d(o){i&&i.d(o)}}}function ke(t){let e;return{c(){e=Z(t[1])},l(l){e=x(l,t[1])},m(l,i){j(l,e,i)},p(l,i){i&2&&ee(e,l[1])},i:K,o:K,d(l){l&&g(e)}}}function ye(t){let e,l,i,o;const a=[ke,ge],f=[];function u(s,n){return s[1]?0:1}return e=u(t),l=f[e]=a[e](t),{c(){l.c(),i=J()},l(s){l.l(s),i=J()},m(s,n){f[e].m(s,n),j(s,i,n),o=!0},p(s,n){let c=e;e=u(s),e===c?f[e].p(s,n):(Q(),N(f[c],1,1,()=>{f[c]=null}),W(),l=f[e],l?l.p(s,n):(l=f[e]=a[e](s),l.c()),C(l,1),l.m(i.parentNode,i))},i(s){o||(C(l),o=!0)},o(s){N(l),o=!1},d(s){s&&g(i),f[e].d(s)}}}function ve(t){let e;const l=t[17].default,i=T(l,t,t[16],null);return{c(){i&&i.c()},l(o){i&&i.l(o)},m(o,a){i&&i.m(o,a),e=!0},p(o,a){i&&i.p&&(!e||a&65536)&&z(i,l,o,o[16],e?O(l,o[16],a,null):A(o[16]),null)},i(o){e||(C(i,o),e=!0)},o(o){N(i,o),e=!1},d(o){i&&i.d(o)}}}function Ne(t){let e;return{c(){e=Z(t[1])},l(l){e=x(l,t[1])},m(l,i){j(l,e,i)},p(l,i){i&2&&ee(e,l[1])},i:K,o:K,d(l){l&&g(e)}}}function Ce(t){let e,l,i,o;const a=[_e,be],f=[];function u(s,n){return s[3]?0:1}return e=u(t),l=f[e]=a[e](t),{c(){l.c(),i=J()},l(s){l.l(s),i=J()},m(s,n){f[e].m(s,n),j(s,i,n),o=!0},p(s,[n]){let c=e;e=u(s),e===c?f[e].p(s,n):(Q(),N(f[c],1,1,()=>{f[c]=null}),W(),l=f[e],l?l.p(s,n):(l=f[e]=a[e](s),l.c()),C(l,1),l.m(i.parentNode,i))},i(s){o||(C(l),o=!0)},o(s){N(l),o=!1},d(s){s&&g(i),f[e].d(s)}}}function Ee(t,e,l){let i,o,a;const f=["class","active","block","children","close","color","disabled","href","inner","outline","size","value"];let u=S(e,f),{$$slots:s={},$$scope:n}=e,{class:c=""}=e,{active:d=!1}=e,{block:r=!1}=e,{children:b=""}=e,{close:h=!1}=e,{color:_="secondary"}=e,{disabled:k=!1}=e,{href:E=""}=e,{inner:B=void 0}=e,{outline:G=!1}=e,{size:H=""}=e,{value:w=""}=e;function ne(m){U.call(this,t,m)}function ie(m){U.call(this,t,m)}function oe(m){Y[m?"unshift":"push"](()=>{B=m,l(0,B)})}function ue(m){Y[m?"unshift":"push"](()=>{B=m,l(0,B)})}return t.$$set=m=>{l(22,e=y(y({},e),V(m))),l(8,u=S(e,f)),"class"in m&&l(9,c=m.class),"active"in m&&l(10,d=m.active),"block"in m&&l(11,r=m.block),"children"in m&&l(1,b=m.children),"close"in m&&l(12,h=m.close),"color"in m&&l(13,_=m.color),"disabled"in m&&l(2,k=m.disabled),"href"in m&&l(3,E=m.href),"inner"in m&&l(0,B=m.inner),"outline"in m&&l(14,G=m.outline),"size"in m&&l(15,H=m.size),"value"in m&&l(4,w=m.value),"$$scope"in m&&l(16,n=m.$$scope)},t.$$.update=()=>{l(7,i=e["aria-label"]),t.$$.dirty&65024&&l(6,o=q(c,h?"btn-close":"btn",h||`btn${G?"-outline":""}-${_}`,H?`btn-${H}`:!1,r?"d-block w-100":!1,{active:d})),t.$$.dirty&4096&&l(5,a=h?"Close":null)},e=V(e),[B,b,k,E,w,a,o,i,u,c,d,r,h,_,G,H,n,s,ne,ie,oe,ue]}class tl extends F{constructor(e){super(),R(this,e,Ee,Ce,L,{class:9,active:10,block:11,children:1,close:12,color:13,disabled:2,href:3,inner:0,outline:14,size:15,value:4})}}function Se(t){let e,l,i,o;const a=t[9].default,f=T(a,t,t[8],null);let u=[t[2],{"data-bs-theme":t[0]},{class:t[1]}],s={};for(let n=0;n<u.length;n+=1)s=y(s,u[n]);return{c(){e=I("div"),f&&f.c(),this.h()},l(n){e=P(n,"DIV",{"data-bs-theme":!0,class:!0});var c=D(e);f&&f.l(c),c.forEach(g),this.h()},h(){v(e,s)},m(n,c){j(n,e,c),f&&f.m(e,null),l=!0,i||(o=X(e,"click",t[10]),i=!0)},p(n,[c]){f&&f.p&&(!l||c&256)&&z(f,a,n,n[8],l?O(a,n[8],c,null):A(n[8]),null),v(e,s=M(u,[c&4&&n[2],(!l||c&1)&&{"data-bs-theme":n[0]},(!l||c&2)&&{class:n[1]}]))},i(n){l||(C(f,n),l=!0)},o(n){N(f,n),l=!1},d(n){n&&g(e),f&&f.d(n),i=!1,o()}}}function je(t,e,l){let i;const o=["class","body","color","inverse","outline","theme"];let a=S(e,o),{$$slots:f={},$$scope:u}=e,{class:s=""}=e,{body:n=!1}=e,{color:c=""}=e,{inverse:d=!1}=e,{outline:r=!1}=e,{theme:b=void 0}=e;function h(_){U.call(this,t,_)}return t.$$set=_=>{e=y(y({},e),V(_)),l(2,a=S(e,o)),"class"in _&&l(3,s=_.class),"body"in _&&l(4,n=_.body),"color"in _&&l(5,c=_.color),"inverse"in _&&l(6,d=_.inverse),"outline"in _&&l(7,r=_.outline),"theme"in _&&l(0,b=_.theme),"$$scope"in _&&l(8,u=_.$$scope)},t.$$.update=()=>{t.$$.dirty&248&&l(1,i=q(s,"card",d?"text-white":!1,n?"card-body":!1,c?`${r?"border":"bg"}-${c}`:!1))},[b,i,a,s,n,c,d,r,u,f,h]}class sl extends F{constructor(e){super(),R(this,e,je,Se,L,{class:3,body:4,color:5,inverse:6,outline:7,theme:0})}}function Ie(t){let e,l;const i=t[4].default,o=T(i,t,t[3],null);let a=[t[1],{class:t[0]}],f={};for(let u=0;u<a.length;u+=1)f=y(f,a[u]);return{c(){e=I("div"),o&&o.c(),this.h()},l(u){e=P(u,"DIV",{class:!0});var s=D(e);o&&o.l(s),s.forEach(g),this.h()},h(){v(e,f)},m(u,s){j(u,e,s),o&&o.m(e,null),l=!0},p(u,[s]){o&&o.p&&(!l||s&8)&&z(o,i,u,u[3],l?O(i,u[3],s,null):A(u[3]),null),v(e,f=M(a,[s&2&&u[1],(!l||s&1)&&{class:u[0]}]))},i(u){l||(C(o,u),l=!0)},o(u){N(o,u),l=!1},d(u){u&&g(e),o&&o.d(u)}}}function Pe(t,e,l){let i;const o=["class"];let a=S(e,o),{$$slots:f={},$$scope:u}=e,{class:s=""}=e;return t.$$set=n=>{e=y(y({},e),V(n)),l(1,a=S(e,o)),"class"in n&&l(2,s=n.class),"$$scope"in n&&l(3,u=n.$$scope)},t.$$.update=()=>{t.$$.dirty&4&&l(0,i=q(s,"card-body"))},[i,a,s,u,f]}class nl extends F{constructor(e){super(),R(this,e,Pe,Ie,L,{class:2})}}function De(t){let e,l,i,o;const a=t[5].default,f=T(a,t,t[4],null);let u=[t[2],{class:t[1]}],s={};for(let n=0;n<u.length;n+=1)s=y(s,u[n]);return{c(){e=I("div"),f&&f.c(),this.h()},l(n){e=P(n,"DIV",{class:!0});var c=D(e);f&&f.l(c),c.forEach(g),this.h()},h(){v(e,s)},m(n,c){j(n,e,c),f&&f.m(e,null),l=!0,i||(o=X(e,"click",t[7]),i=!0)},p(n,c){f&&f.p&&(!l||c&16)&&z(f,a,n,n[4],l?O(a,n[4],c,null):A(n[4]),null),v(e,s=M(u,[c&4&&n[2],(!l||c&2)&&{class:n[1]}]))},i(n){l||(C(f,n),l=!0)},o(n){N(f,n),l=!1},d(n){n&&g(e),f&&f.d(n),i=!1,o()}}}function Te(t){let e,l,i,o;const a=t[5].default,f=T(a,t,t[4],null);let u=[t[2],{class:t[1]}],s={};for(let n=0;n<u.length;n+=1)s=y(s,u[n]);return{c(){e=I("h3"),f&&f.c(),this.h()},l(n){e=P(n,"H3",{class:!0});var c=D(e);f&&f.l(c),c.forEach(g),this.h()},h(){v(e,s)},m(n,c){j(n,e,c),f&&f.m(e,null),l=!0,i||(o=X(e,"click",t[6]),i=!0)},p(n,c){f&&f.p&&(!l||c&16)&&z(f,a,n,n[4],l?O(a,n[4],c,null):A(n[4]),null),v(e,s=M(u,[c&4&&n[2],(!l||c&2)&&{class:n[1]}]))},i(n){l||(C(f,n),l=!0)},o(n){N(f,n),l=!1},d(n){n&&g(e),f&&f.d(n),i=!1,o()}}}function ze(t){let e,l,i,o;const a=[Te,De],f=[];function u(s,n){return s[0]==="h3"?0:1}return e=u(t),l=f[e]=a[e](t),{c(){l.c(),i=J()},l(s){l.l(s),i=J()},m(s,n){f[e].m(s,n),j(s,i,n),o=!0},p(s,[n]){let c=e;e=u(s),e===c?f[e].p(s,n):(Q(),N(f[c],1,1,()=>{f[c]=null}),W(),l=f[e],l?l.p(s,n):(l=f[e]=a[e](s),l.c()),C(l,1),l.m(i.parentNode,i))},i(s){o||(C(l),o=!0)},o(s){N(l),o=!1},d(s){s&&g(i),f[e].d(s)}}}function Ae(t,e,l){let i;const o=["class","tag"];let a=S(e,o),{$$slots:f={},$$scope:u}=e,{class:s=""}=e,{tag:n="div"}=e;function c(r){U.call(this,t,r)}function d(r){U.call(this,t,r)}return t.$$set=r=>{e=y(y({},e),V(r)),l(2,a=S(e,o)),"class"in r&&l(3,s=r.class),"tag"in r&&l(0,n=r.tag),"$$scope"in r&&l(4,u=r.$$scope)},t.$$.update=()=>{t.$$.dirty&8&&l(1,i=q(s,"card-header"))},[n,i,a,s,u,f,c,d]}class il extends F{constructor(e){super(),R(this,e,Ae,ze,L,{class:3,tag:0})}}function Oe(t){let e,l;const i=t[4].default,o=T(i,t,t[3],null);let a=[t[1],{class:t[0]}],f={};for(let u=0;u<a.length;u+=1)f=y(f,a[u]);return{c(){e=I("h5"),o&&o.c(),this.h()},l(u){e=P(u,"H5",{class:!0});var s=D(e);o&&o.l(s),s.forEach(g),this.h()},h(){v(e,f)},m(u,s){j(u,e,s),o&&o.m(e,null),l=!0},p(u,[s]){o&&o.p&&(!l||s&8)&&z(o,i,u,u[3],l?O(i,u[3],s,null):A(u[3]),null),v(e,f=M(a,[s&2&&u[1],(!l||s&1)&&{class:u[0]}]))},i(u){l||(C(o,u),l=!0)},o(u){N(o,u),l=!1},d(u){u&&g(e),o&&o.d(u)}}}function Be(t,e,l){let i;const o=["class"];let a=S(e,o),{$$slots:f={},$$scope:u}=e,{class:s=""}=e;return t.$$set=n=>{e=y(y({},e),V(n)),l(1,a=S(e,o)),"class"in n&&l(2,s=n.class),"$$scope"in n&&l(3,u=n.$$scope)},t.$$.update=()=>{t.$$.dirty&4&&l(0,i=q(s,"card-title"))},[i,a,s,u,f]}class ol extends F{constructor(e){super(),R(this,e,Be,Oe,L,{class:2})}}function Me(t){let e,l,i;const o=t[10].default,a=T(o,t,t[9],null);let f=[t[1],{class:l=t[0].join(" ")}],u={};for(let s=0;s<f.length;s+=1)u=y(u,f[s]);return{c(){e=I("div"),a&&a.c(),this.h()},l(s){e=P(s,"DIV",{class:!0});var n=D(e);a&&a.l(n),n.forEach(g),this.h()},h(){v(e,u)},m(s,n){j(s,e,n),a&&a.m(e,null),i=!0},p(s,[n]){a&&a.p&&(!i||n&512)&&z(a,o,s,s[9],i?O(o,s[9],n,null):A(s[9]),null),v(e,u=M(f,[n&2&&s[1],{class:l}]))},i(s){i||(C(a,s),i=!0)},o(s){N(a,s),i=!1},d(s){s&&g(e),a&&a.d(s)}}}function Ve(t,e,l){const i=["class","xs","sm","md","lg","xl","xxl"];let o=S(e,i),{$$slots:a={},$$scope:f}=e,{class:u=""}=e,{xs:s=void 0}=e,{sm:n=void 0}=e,{md:c=void 0}=e,{lg:d=void 0}=e,{xl:r=void 0}=e,{xxl:b=void 0}=e;const h=[],_={xs:s,sm:n,md:c,lg:d,xl:r,xxl:b};return Object.keys(_).forEach(k=>{const E=_[k];if(!E&&E!=="")return;const B=k==="xs";if(me(E)){const G=B?"-":`-${k}-`,H=$(B,k,E.size);(E.size||E.size==="")&&h.push(H),E.push&&h.push(`push${G}${E.push}`),E.pull&&h.push(`pull${G}${E.pull}`),E.offset&&h.push(`offset${G}${E.offset}`),E.order&&h.push(`order${G}${E.order}`)}else h.push($(B,k,E))}),h.length||h.push("col"),u&&h.push(u),t.$$set=k=>{e=y(y({},e),V(k)),l(1,o=S(e,i)),"class"in k&&l(2,u=k.class),"xs"in k&&l(3,s=k.xs),"sm"in k&&l(4,n=k.sm),"md"in k&&l(5,c=k.md),"lg"in k&&l(6,d=k.lg),"xl"in k&&l(7,r=k.xl),"xxl"in k&&l(8,b=k.xxl),"$$scope"in k&&l(9,f=k.$$scope)},[h,o,u,s,n,c,d,r,b,f,a]}class ul extends F{constructor(e){super(),R(this,e,Ve,Me,L,{class:2,xs:3,sm:4,md:5,lg:6,xl:7,xxl:8})}}function Ge(t){let e,l;const i=t[8].default,o=T(i,t,t[7],null);let a=[t[2],{class:t[1]}],f={};for(let u=0;u<a.length;u+=1)f=y(f,a[u]);return{c(){e=I("div"),o&&o.c(),this.h()},l(u){e=P(u,"DIV",{class:!0});var s=D(e);o&&o.l(s),s.forEach(g),this.h()},h(){v(e,f)},m(u,s){j(u,e,s),o&&o.m(e,null),t[9](e),l=!0},p(u,[s]){o&&o.p&&(!l||s&128)&&z(o,i,u,u[7],l?O(i,u[7],s,null):A(u[7]),null),v(e,f=M(a,[s&4&&u[2],(!l||s&2)&&{class:u[1]}]))},i(u){l||(C(o,u),l=!0)},o(u){N(o,u),l=!1},d(u){u&&g(e),o&&o.d(u),t[9](null)}}}function Le(t){const e=parseInt(t);if(isNaN(e)){if(typeof t=="object")return["xs","sm","md","lg","xl"].map(l=>{const o=l==="xs"?"-":`-${l}-`,a=t[l];return typeof a=="number"&&a>0?`row-cols${o}${a}`:null}).filter(l=>!!l)}else if(e>0)return[`row-cols-${e}`];return[]}function Fe(t,e,l){let i;const o=["class","noGutters","form","cols","inner"];let a=S(e,o),{$$slots:f={},$$scope:u}=e,{class:s=""}=e,{noGutters:n=!1}=e,{form:c=!1}=e,{cols:d=0}=e,{inner:r=void 0}=e;function b(h){Y[h?"unshift":"push"](()=>{r=h,l(0,r)})}return t.$$set=h=>{e=y(y({},e),V(h)),l(2,a=S(e,o)),"class"in h&&l(3,s=h.class),"noGutters"in h&&l(4,n=h.noGutters),"form"in h&&l(5,c=h.form),"cols"in h&&l(6,d=h.cols),"inner"in h&&l(0,r=h.inner),"$$scope"in h&&l(7,u=h.$$scope)},t.$$.update=()=>{t.$$.dirty&120&&l(1,i=q(s,n?"gx-0":null,c?"form-row":"row",...Le(d)))},[r,i,a,s,n,c,d,u,f,b]}class fl extends F{constructor(e){super(),R(this,e,Fe,Ge,L,{class:3,noGutters:4,form:5,cols:6,inner:0})}}function Re(t){let e;return{c(){e=Z("Loading...")},l(l){e=x(l,"Loading...")},m(l,i){j(l,e,i)},d(l){l&&g(e)}}}function qe(t){let e,l,i;const o=t[7].default,a=T(o,t,t[6],null),f=a||Re();let u=[t[1],{role:"status"},{class:t[0]}],s={};for(let n=0;n<u.length;n+=1)s=y(s,u[n]);return{c(){e=I("div"),l=I("span"),f&&f.c(),this.h()},l(n){e=P(n,"DIV",{role:!0,class:!0});var c=D(e);l=P(c,"SPAN",{class:!0});var d=D(l);f&&f.l(d),d.forEach(g),c.forEach(g),this.h()},h(){fe(l,"class","visually-hidden"),v(e,s)},m(n,c){j(n,e,c),ae(e,l),f&&f.m(l,null),i=!0},p(n,[c]){a&&a.p&&(!i||c&64)&&z(a,o,n,n[6],i?O(o,n[6],c,null):A(n[6]),null),v(e,s=M(u,[c&2&&n[1],{role:"status"},(!i||c&1)&&{class:n[0]}]))},i(n){i||(C(f,n),i=!0)},o(n){N(f,n),i=!1},d(n){n&&g(e),f&&f.d(n)}}}function He(t,e,l){let i;const o=["class","type","size","color"];let a=S(e,o),{$$slots:f={},$$scope:u}=e,{class:s=""}=e,{type:n="border"}=e,{size:c=""}=e,{color:d=""}=e;return t.$$set=r=>{e=y(y({},e),V(r)),l(1,a=S(e,o)),"class"in r&&l(2,s=r.class),"type"in r&&l(3,n=r.type),"size"in r&&l(4,c=r.size),"color"in r&&l(5,d=r.color),"$$scope"in r&&l(6,u=r.$$scope)},t.$$.update=()=>{t.$$.dirty&60&&l(0,i=q(s,c?`spinner-${n}-${c}`:!1,`spinner-${n}`,d?`text-${d}`:!1))},[i,a,s,n,c,d,u,f]}class al extends F{constructor(e){super(),R(this,e,He,qe,L,{class:2,type:3,size:4,color:5})}}const se=ce(Je());se.subscribe(t=>Ue(t));function Je(){var l,i,o;const t=((l=globalThis.document)==null?void 0:l.documentElement.getAttribute("data-bs-theme"))||"light",e=typeof((i=globalThis.window)==null?void 0:i.matchMedia)=="function"?(o=globalThis.window)==null?void 0:o.matchMedia("(prefers-color-scheme: dark)").matches:!1;return t==="dark"||t==="auto"&&e?"dark":"light"}function Ue(t,e){var i;let l=t;if(arguments.length===1){if(l=(i=globalThis.document)==null?void 0:i.documentElement,!l)return;e=t,se.update(()=>e)}l.setAttribute("data-bs-theme",e)}export{tl as B,sl as C,fl as R,al as S,il as a,nl as b,q as c,ol as d,xe as e,We as f,M as g,ul as h,Ye as i,el as j,we as k,pe as l,$e as m,Ze as p,de as s,ll as u};