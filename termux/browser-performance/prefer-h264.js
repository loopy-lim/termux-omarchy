// GPU composition does not imply hardware video decode in an Android PRoot.
// Restrict only YouTube's expensive AV1/VP9 choices; retain original API semantics.
(() => {
  if (!['www.youtube.com', 'm.youtube.com'].includes(location.hostname)) return;
  const expensive = type => typeof type === 'string' && /\b(?:av01|vp0?9)(?:[.\s,";]|$)/i.test(type);
  const patch = (owner, name, unsupported) => {
    if (!owner || typeof owner[name] !== 'function') return;
    const original = owner[name];
    owner[name] = function (type, ...args) {
      return expensive(type) ? unsupported : Reflect.apply(original, this, [type, ...args]);
    };
  };
  patch(HTMLMediaElement.prototype, 'canPlayType', '');
  patch(globalThis.MediaSource, 'isTypeSupported', false);
  patch(globalThis.ManagedMediaSource, 'isTypeSupported', false);
})();
