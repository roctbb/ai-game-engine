<template>
  <span class="arena-bot" aria-hidden="true"
    ><i class="arena-bot-body"></i><i class="arena-bot-antenna"></i
    ><i class="arena-bot-eyes"></i
  ></span>
</template>
<style>
.arena-bot {
  display: inline-block;
  position: relative;
  width: 1em;
  height: 1em;
  font-size: 30px;
  flex: none;
  color: var(--agp-primary);
}
.arena-bot-body {
  position: absolute;
  left: 11%;
  top: 24%;
  width: 78%;
  height: 70%;
  background: currentColor;
  border-radius: 16% 16% 16% 4%;
}
.arena-bot-body:before {
  content: "";
  position: absolute;
  left: -14%;
  top: 40%;
  width: 21%;
  height: 28%;
  background: currentColor;
}
.arena-bot-antenna {
  position: absolute;
  left: 60%;
  top: 0;
  width: 16%;
  height: 16%;
  background: var(--arena-yellow);
}
.arena-bot-eyes {
  position: absolute;
  left: 31%;
  top: 46%;
  width: 10%;
  height: 15%;
  background: var(--agp-surface);
  box-shadow: 0.28em 0 var(--agp-surface);
}
</style>
