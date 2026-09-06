// scroll swap — toggle is-sticky on the header so the bear crossfades to the Park City alt logo past 40px scroll
(function(){
  var header=document.querySelector('.kodiak-header');
  if(!header) return;
  var onScroll=function(){
    if((window.scrollY||window.pageYOffset||0)>40) header.classList.add('is-sticky');
    else header.classList.remove('is-sticky');
  };
  window.addEventListener('scroll', onScroll, {passive:true});
  onScroll();
})();
