const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const script = fs.readFileSync(path.join(__dirname, '../assets/analytics.js'), 'utf8');

function simulate(tracker = true) {
  const events = [], winListeners = {}, audioListeners = {};
  const state = {top: 900, played: []};
  const audio = {duration: 100, currentTime: 0,
    played: {get length(){return state.played.length;},
      start(i){return state.played[i][0];}, end(i){return state.played[i][1];}},
    addEventListener(name, fn){audioListeners[name]=fn;}};
  const page = {dataset:{reviewSlug:'test-review'}, querySelector(q){
    return q==='audio' ? audio : q==='.prose' ?
      {getBoundingClientRect:()=>({top:state.top,height:1000})} : null;
  }};
  const win = {innerHeight:500, umami:tracker ? {track:(name,data)=>events.push([name,data])} : undefined,
    addEventListener(name,fn){winListeners[name]=fn;}, requestAnimationFrame(fn){fn();}};
  vm.runInNewContext(script,{document:{querySelector:()=>page,visibilityState:'visible'},window:win});
  return {events,state,audio,winListeners,audioListeners};
}
const s=simulate();
s.audioListeners.playing();s.audioListeners.playing();
s.audio.currentTime=99;s.state.played=[[98,100]];s.audioListeners.ended();
assert.equal(s.events.filter(x=>x[0]==='audio-play').length,1);
assert.equal(s.events.filter(x=>x[0]==='audio-complete').length,0);
s.state.played=[[0,80],[98,100]];s.audioListeners.timeupdate();
assert.equal(s.events.filter(x=>x[0]==='audio-progress').length,3);
s.state.played=[[0,98]];s.audioListeners.timeupdate();s.audioListeners.ended();
assert.equal(s.events.filter(x=>x[0]==='audio-complete').length,1);
s.state.top=0;s.winListeners.scroll();s.winListeners.scroll();
assert.equal(s.events.filter(x=>x[0]==='review-scroll').length,2);
s.state.top=-500;s.winListeners.scroll();
assert.equal(s.events.filter(x=>x[0]==='review-scroll').length,4);
assert.equal(s.events.every(x=>x[1].review==='test-review'),true);
const blocked=simulate(false);blocked.audioListeners.playing();blocked.winListeners.scroll();
assert.equal(blocked.events.length,0);
console.log('Analytics event behaviour passed');
