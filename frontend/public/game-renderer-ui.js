/* Optional presentation layer. Existing renderer state messages are unchanged. */
(() => {
  if (document.documentElement.dataset.agpEnhanced === 'true') return;
  const names = {
    keys:'Ключей',collected:'Собрано',keys_collected:'Собрано ключей',escaped:'Выход',score:'Счёт',
    water:'Вода',water_cells:'Затоплено клеток',alive:'Бот жив',invalid:'Ошибочных ходов',invalid_moves:'Ошибочных ходов',
    pairs:'Пар порталов',lit:'Зажжено',left:'Осталось',visible:'Видно клеток',switched:'Переключено',
    planks:'Доски',oxygen:'Кислород',refills:'Пополнений',battery:'Заряд',fuel:'Топливо',ore:'Руда',
    carrying:'Груз',coins:'Монеты',apples:'Яблоки',turn:'Ход',tick:'Ход',turns:'Ходов',steps:'Шагов',
    rescued:'Спасено',cleaned:'Убрано',remaining:'Осталось',energy:'Энергия',health:'Здоровье',
    lives:'Жизни',gates:'Ворот',boxes:'Ящики',buttons:'Кнопки',delivered:'Доставлено',harvest:'Урожай',
    lamps:'Лампы',mode:'Режим',coins_left:'Осталось монет',flags:'Флаги',mines:'Мины',revealed:'Открыто',
  };
  function updateHUD() {
    const hud = document.getElementById('hud');
    if (!hud) return;
    const walker = document.createTreeWalker(hud, NodeFilter.SHOW_TEXT);
    const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);
    for (const node of nodes) node.textContent=node.textContent.replace(/\b([a-z_]+)=([^\s]+)/g,(_,key,value)=>`${names[key]||key}: ${value==='true'?'да':value==='false'?'нет':value==='-'?'—':value}`);
  }
  // Cell meanings are taken from the existing player guides.
  const legends={"pacman_v1":{"-1":"стена","0":"пустая клетка","1":"обычная точка","2":"большая точка: на несколько ходов позволяет съедать призраков","-2":"призрак"},"flood_escape_v1":{"-1":"стена","-2":"вода, в нее нельзя идти","0":"пустая клетка","1":"выход"},"courier_v1":{"-1":"стена или здание, туда ходить нельзя","0":"дорога","1":"посылка","2":"пункт доставки"},"coins_right_down_v1":{"-1":"стена","0":"пустая клетка","1":"монета","2":"финиш"},"conveyor_escape_v1":{"-1":"стена;","0":"пустая клетка;","1":"выход;","2":"конвейер вверх;","3":"конвейер вправо;","4":"конвейер вниз;","5":"конвейер влево"},"portal_escape_v1":{"-1":"стена","0":"пустая клетка","1":"выход"},"minesweeper_v1":{"-2":"закрытая клетка","-1":"ваш флаг"},"oxygen_maze_v1":{"-1":"стена","0":"пустая клетка","1":"станция кислорода","2":"выход"},"switch_maze_v1":{"-1":"стена","-2":"закрытая дверь","0":"пустая клетка","1":"переключатель","2":"выход"},"knight_coins_v1":{"-1":"стена или яма;","0":"пустая клетка;","1":"монета;","2":"выход"},"gate_keys_v1":{"-1":"стена;","-2":"закрытые ворота;","0":"пустая клетка;","1":"ключ;","2":"выход"},"garden_harvest_v1":{"-1":"стена","0":"пустая клетка","1":"урожай","2":"сарай"},"box_buttons_v1":{"-1":"стена;","0":"пустая клетка;","1":"ящик;","2":"кнопка;","3":"ящик уже стоит на кнопке"},"fire_rescue_v1":{"-1":"стена, сюда нельзя ходить","0":"пустая клетка","1":"пожар","2":"источник воды"},"road_crossing_v1":{"-1":"машина;","0":"пустая клетка;","1":"финиш"},"robot_vacuum_v1":{"-1":"стена","0":"чистая клетка","1":"грязь","2":"зарядка"},"jump_maze_v1":{"-1":"стена;","0":"обычная клетка;","1":"выход;","2":"с этой клетки надо прыгнуть на 2 клетки;","3":"с этой клетки надо прыгнуть на 3 клетки"},"space_miner_v1":{"-1":"стена или астероидная скала","0":"пустая клетка","1":"руда","2":"база для заправки"},"river_planks_v1":{"-1":"стена","-2":"вода","0":"пустая клетка","1":"доска, которую можно подобрать","2":"выход"},"blinking_bridge_v1":{"-2":"закрытый мост;","-1":"стена;","0":"пустая клетка;","1":"выход;","2":"открытый мост"},"crystal_lamps_v1":{"-9":"неизвестная клетка вне видимости","-1":"стена","0":"пустая клетка","1":"незажженный маяк","2":"выход","3":"зажженный маяк"},"ice_slide_v1":{"-1":"стена","0":"лед","1":"выход"},"snake_v1":{"0":"пустая клетка","1":"еда","-1":"препятствие: край поля, тело змейки или камень"}};
  let frame={},gameSlug="";
  function addLegend() {
    const labels=legends[gameSlug],svg=document.getElementById('board');
    if(!labels||!svg||document.getElementById('agp-renderer-legend'))return;
    const legend=document.createElement('div');legend.id='agp-renderer-legend';legend.setAttribute('aria-label','Обозначения карты');
    Object.assign(legend.style,{display:'flex',flexWrap:'wrap',gap:'4px 12px',font:'11px/1.5 system-ui,sans-serif',color:'#b6c5d8',marginTop:'8px'});
    Object.entries(labels).slice(0,8).forEach(([value,label])=>{const item=document.createElement('span');item.textContent=`${value} — ${label}`;legend.append(item)});
    (svg.closest('.wrap')||svg.parentElement).append(legend);
    const tip=document.createElement('div');tip.hidden=true;Object.assign(tip.style,{position:'fixed',top:'8px',left:'8px',zIndex:'20',padding:'5px 8px',borderRadius:'5px',background:'#081524ee',color:'#e8f2ff',font:'12px system-ui,sans-serif',pointerEvents:'none'});document.body.append(tip);
    svg.addEventListener('pointermove',event=>{const board=Array.isArray(frame.board)?frame.board:frame.maze;if(!Array.isArray(board)||!Array.isArray(board[0]))return;const matrix=svg.getScreenCTM();if(!matrix)return;const point=new DOMPoint(event.clientX,event.clientY).matrixTransform(matrix.inverse()),box=svg.viewBox.baseVal,x=Math.floor((point.x-box.x)*board.length/box.width),y=Math.floor((point.y-box.y)*board[0].length/box.height);if(x<0||y<0||x>=board.length||y>=board[0].length){tip.hidden=true;return}const value=board[x][y];tip.textContent=`(${x}, ${y}) · ${labels[String(value)]||`значение ${value}`}`;tip.hidden=false});svg.addEventListener('pointerleave',()=>{tip.hidden=true});
  }

  function fit() {
    const svg=document.getElementById('board'),wrap=svg?.closest('.wrap');
    const board=Array.isArray(frame.board)?frame.board:frame.maze;
    if(!svg||!wrap||!Array.isArray(board)||!Array.isArray(board[0]))return;
    const w=board.length,h=board[0].length;
    if(!w||!h)return;
    svg.style.aspectRatio=`${w}/${h}`;
    const reserve=(document.getElementById('hud')?.offsetHeight||24)+(document.getElementById('agp-renderer-legend')?.offsetHeight||0)+40;
    wrap.style.width=`${Math.max(40,Math.min(innerWidth-24,(innerHeight-reserve)*w/h))}px`;
  }
  window.addEventListener('message',e=>{if(e.source!==parent)return;if(e.data?.type==='agp.renderer.init'){gameSlug=String(e.data.payload?.gameSlug||'');addLegend();fit();return}if(e.data?.type!=='agp.renderer.state')return;frame=e.data.payload?.frame||{};updateHUD();addLegend();fit()});
  window.addEventListener('resize',fit);
  window.addEventListener('keydown',event=>{if(['Space','ArrowLeft','ArrowRight','Digit1','Digit2','Digit3'].includes(event.code)&&!event.ctrlKey&&!event.metaKey&&!event.altKey){event.preventDefault();parent.postMessage({type:'agp.renderer.shortcut',payload:{code:event.code,key:event.key}},'*')}});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',updateHUD);else updateHUD();
})();
