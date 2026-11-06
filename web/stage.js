/* Live2D 舞台脚本：加载 pixi + pixi-live2d-display，失败时保留全息占位动画。 */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const params = new URLSearchParams(window.location.search);
  const modelUrl = (params.get("model") || "").trim();

  // 动作节奏：自动动作的最小间隔（毫秒）；播放速度（1 = 原速，0.9 = 慢 10%）
  const MOTION_COOLDOWN_MS = 3500;
  const MOTION_SPEED = 0.9;

  const state = {
    app: null,
    model: null,
    bridge: null,
    started: false,
    speaking: false,
    mouth: 0,
    mouthTarget: 0,
    lastMotionAt: 0,
    toastTimer: 0,
  };

  const VENDOR = {
    pixi: [
      "vendor/pixi.min.js",
      "https://cdn.jsdelivr.net/npm/pixi.js@6.5.10/dist/browser/pixi.min.js",
    ],
    core: [
      "vendor/live2dcubismcore.min.js",
      "https://cubism.live2d.com/sdk-web/cubismcore/live2dcubismcore.min.js",
    ],
    display: [
      "vendor/pixi-live2d-display-cubism4.min.js",
      "https://cdn.jsdelivr.net/npm/pixi-live2d-display@0.4.0/dist/cubism4.min.js",
    ],
  };

  function setHint(text) {
    const hint = $("hint");
    if (hint) hint.textContent = text;
  }

  function setStageState(text) {
    const badge = $("stage-state");
    if (badge) badge.textContent = text;
  }

  function notify(method, ...args) {
    const bridge = state.bridge;
    if (!bridge || typeof bridge[method] !== "function") return;
    try {
      bridge[method](...args);
    } catch (error) {
      console.warn(`[bridge] ${method} failed`, error);
    }
  }

  function loadScript(src, timeout = 25000) {
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      let settled = false;

      const timer = window.setTimeout(() => {
        if (settled) return;
        settled = true;
        script.remove();
        reject(new Error(`timeout: ${src}`));
      }, timeout);

      script.src = src;
      script.async = false;
      script.onload = () => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timer);
        resolve(src);
      };
      script.onerror = () => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timer);
        script.remove();
        reject(new Error(`failed: ${src}`));
      };

      document.head.appendChild(script);
    });
  }

  async function loadFirst(sources) {
    let lastError = null;
    for (const src of sources) {
      try {
        await loadScript(src);
        return src;
      } catch (error) {
        lastError = error;
        console.warn(error.message);
      }
    }
    throw lastError || new Error("no available source");
  }

  function pulse() {
    document.body.classList.remove("react");
    void document.body.offsetWidth;
    document.body.classList.add("react");
    window.setTimeout(() => document.body.classList.remove("react"), 640);
  }

  function fitModel() {
    const model = state.model;
    const app = state.app;
    if (!model || !app) return;

    const width = app.screen.width;
    const height = app.screen.height;
    const baseWidth = (model.internalModel && model.internalModel.originalWidth) || model.width || 1;
    const baseHeight = (model.internalModel && model.internalModel.originalHeight) || model.height || 1;
    const scale = Math.min(width / baseWidth, height / baseHeight) * 0.93;

    model.scale.set(scale);
    model.anchor.set(0.5, 0.5);
    model.x = width / 2;
    model.y = height * 0.505;
  }

  function playRandomMotion(force = false) {
    const model = state.model;
    if (!model) {
      pulse();
      return;
    }

    // 自动动作在冷却时间内不再打断当前动作；手动按钮传 force=true 跳过
    const now = performance.now();
    if (!force && now - state.lastMotionAt < MOTION_COOLDOWN_MS) {
      return;
    }

    try {
      const manager = model.internalModel && model.internalModel.motionManager;
      const definitions = (manager && manager.definitions) || {};
      const groups = Object.keys(definitions).filter(
        (key) => Array.isArray(definitions[key]) && definitions[key].length > 0
      );
      if (!groups.length) return;

      const preferred = groups.filter((key) => !/idle/i.test(key));
      const pool = preferred.length ? preferred : groups;
      const group = pool[Math.floor(Math.random() * pool.length)];
      const count = definitions[group].length;
      state.lastMotionAt = now;
      model.motion(group, Math.floor(Math.random() * count), 3);
    } catch (error) {
      console.warn("motion failed", error);
    }
  }

  function randomExpression() {
    const model = state.model;
    if (!model) {
      pulse();
      return;
    }

    try {
      const settings = (model.internalModel && model.internalModel.settings) || {};
      const expressions = settings.expressions || [];
      if (!expressions.length) {
        playRandomMotion(true);
        return;
      }
      model.expression(Math.floor(Math.random() * expressions.length));
    } catch (error) {
      console.warn("expression failed", error);
    }
  }

  function showToast(text) {
    const toast = $("toast");
    if (!toast) return;
    toast.textContent = text;
    toast.classList.add("is-visible");
    window.clearTimeout(state.toastTimer);
    state.toastTimer = window.setTimeout(() => toast.classList.remove("is-visible"), 2400);
  }

  function setSpeaking(speaking) {
    state.speaking = Boolean(speaking);
    document.body.classList.toggle("speaking", state.speaking);
    if (!state.speaking) {
      state.mouthTarget = 0;
    }
  }

  function setMouth(value) {
    state.mouthTarget = Math.max(0, Math.min(1, Number(value) || 0));
  }

  async function initModel(url) {
    setHint("正在加载模型…");

    if (!window.PIXI || !PIXI.live2d || !PIXI.live2d.Live2DModel) {
      throw new Error("live2d runtime unavailable");
    }

    const app = new PIXI.Application({
      view: $("canvas"),
      resizeTo: window,
      backgroundAlpha: 0,
      antialias: true,
      autoDensity: true,
      resolution: Math.min(window.devicePixelRatio || 1, 2),
      powerPreference: "high-performance",
    });
    state.app = app;

    const model = await PIXI.live2d.Live2DModel.from(url, { autoInteract: true });
    state.model = model;
    app.stage.addChild(model);

    // 放慢动作播放速度（只影响动作时间轴，不影响口型/眨眼）
    if (MOTION_SPEED !== 1) {
      const manager = model.internalModel && model.internalModel.motionManager;
      if (manager && typeof manager.update === "function") {
        const originalUpdate = manager.update.bind(manager);
        manager.update = (coreModel, deltaTime) =>
          originalUpdate(coreModel, deltaTime * MOTION_SPEED);
      }
    }

    fitModel();
    window.addEventListener("resize", fitModel);

    model.on("hit", () => {
      pulse();
      playRandomMotion();
      notify("onTap");
    });

    // 在参数即将提交给模型前覆盖嘴型，避免被呼吸/动作覆盖
    model.internalModel.on("beforeModelUpdate", () => {
      if (!state.speaking && state.mouth <= 0.001) return;
      const target = state.speaking ? state.mouthTarget : 0;
      state.mouth += (target - state.mouth) * 0.45;
      try {
        model.internalModel.coreModel.setParameterValueById("ParamMouthOpenY", state.mouth);
      } catch (error) {
        /* 模型没有该参数时忽略 */
      }
    });

    const placeholder = $("placeholder");
    if (placeholder) placeholder.classList.add("is-hidden");
    setStageState("LIVE");
    notify("onReady", url.split("/").pop() || "Live2D");
  }

  async function boot() {
    if (!modelUrl) {
      setStageState("NO MODEL");
      setHint("未找到 Live2D 模型 · 将 .model3.json 放进 assets/models/");
      return;
    }

    try {
      setStageState("BOOTING");
      setHint("正在加载渲染运行时…");
      await loadFirst(VENDOR.pixi);
      await loadFirst(VENDOR.core);
      await loadFirst(VENDOR.display);
      await initModel(modelUrl);
    } catch (error) {
      console.error(error);
      setStageState("ERROR");
      setHint(`Live2D 加载失败：${error && error.message ? error.message : error}`);
      notify("onError", String((error && error.message) || error));
    }
  }

  function start() {
    if (state.started) return;
    state.started = true;
    boot();
  }

  window.Live2DStage = {
    randomMotion(force = false) {
      playRandomMotion(force);
    },
    randomExpression,
    react() {
      pulse();
      playRandomMotion();
    },
    showToast,
    setSpeaking,
    setMouth,
  };

  if (typeof QWebChannel !== "undefined" && typeof qt !== "undefined" && qt.webChannelTransport) {
    new QWebChannel(qt.webChannelTransport, (channel) => {
      state.bridge = (channel.objects && channel.objects.stage) || null;
      start();
    });
    window.setTimeout(start, 1500);
  } else {
    start();
  }
})();
