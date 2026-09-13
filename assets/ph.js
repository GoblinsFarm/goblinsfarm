/* Goblins Farm site analytics (PostHog). One file, loaded on every page.
   Identity lives in localStorage only (no cookies). Edit config here, not in pages. */
(function () {
  var TOKEN = "phc_sjkQe5EkSxzEgqGrRnPmrTewuTGdSkMUhvhxAjEFBVRV";
  var HOST = "https://us.i.posthog.com";
  if (!TOKEN || TOKEN.indexOf("phc_") !== 0) return;

  // Official snippet: stubs posthog.* until array.js arrives.
  !function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="init capture register register_once register_for_session unregister unregister_for_session getFeatureFlag getFeatureFlagPayload isFeatureEnabled reloadFeatureFlags updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures on onFeatureFlags onSurveysLoaded onSessionId getSurveys getActiveMatchingSurveys renderSurvey canRenderSurvey canRenderSurveyAsync identify setPersonProperties group resetGroups setPersonPropertiesForFlags resetPersonPropertiesForFlags setGroupPropertiesForFlags resetGroupPropertiesForFlags reset get_distinct_id getGroups get_session_id get_session_replay_url alias set_config startSessionRecording stopSessionRecording sessionRecordingStarted captureException loadToolbar get_property getSessionProperty createPersonProfile opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing clear_opt_in_out_capturing is_capturing getFeatureFlags getFeatureFlagPayloads calculateEventProperties".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);

  posthog.init(TOKEN, {
    api_host: HOST,
    defaults: "2026-05-30",
    persistence: "localStorage",
    person_profiles: "identified_only",
    capture_pageview: true,
    capture_pageleave: true,
    capture_performance: true,
    capture_heatmaps: true,
    autocapture: true,
    rageclick: true,
    session_recording: { maskAllInputs: true, maskTextSelector: ".key" }
  });

  // Section of the site, so traffic splits cleanly in insights.
  var path = location.pathname;
  var section = path === "/" || path === "/index.html" ? "home"
    : path.indexOf("/wiki/") === 0 ? "wiki"
    : path.indexOf("/tutorials/") === 0 ? "tutorials"
    : path.indexOf("/guides/") === 0 ? "guides"
    : path.indexOf("/news/") === 0 ? "news"
    : path.indexOf("/thanks") === 0 ? "thanks" : "other";
  posthog.register({ site_section: section });

  // Buy and download clicks, in addition to autocapture.
  document.addEventListener("click", function (ev) {
    var a = ev.target && ev.target.closest ? ev.target.closest("a[href]") : null;
    if (!a) return;
    var href = a.getAttribute("href") || "";
    if (href.indexOf("/v1/checkout") !== -1) {
      var product = (href.match(/product=([a-z]+)/) || [])[1] || "main";
      try { localStorage.setItem("gf_checkout_product", product); } catch (e) {}
      posthog.capture("checkout_click", { product: product, button_text: (a.textContent || "").trim(), page: path });
    } else if (a.id === "dl-mac" || a.id === "dl-win" || /\.(dmg|exe)$/.test(href) || href.indexOf("/releases") !== -1) {
      var platform = a.id === "dl-mac" || /\.dmg$/.test(href) ? "mac" : a.id === "dl-win" || /\.exe$/.test(href) ? "windows" : "unknown";
      posthog.capture("download_click", { platform: platform, href: href, page: path });
    } else if (/^https?:\/\//.test(href) && href.indexOf(location.host) === -1) {
      posthog.capture("outbound_click", { href: href, page: path });
    }
  }, true);
})();
