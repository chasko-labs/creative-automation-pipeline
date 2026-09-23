// scroll swap — toggle is-sticky on the header so the bear crossfades to the Park City alt logo past 20px scroll.
// Listens on window AND the desktop scroll panel (.wrap owns scrolling under the no-scroll load frame).
(function(){
  var header=document.querySelector('.kodiak-header');
  if(!header) return;
  var panel=document.querySelector('.wrap');
  var past=function(){ return ((window.scrollY||window.pageYOffset||0)>20) || (panel && panel.scrollTop>20); };
  var onScroll=function(){
    if(past()) header.classList.add('is-sticky');
    else header.classList.remove('is-sticky');
  };
  window.addEventListener('scroll', onScroll, {passive:true});
  if(panel) panel.addEventListener('scroll', onScroll, {passive:true});
  onScroll();
})();
