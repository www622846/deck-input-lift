/* SPDX-License-Identifier: MIT */
(function () {
    "use strict";
    var pending;
    function focused() {
        var element = document.activeElement;
        while (element && element.shadowRoot && element.shadowRoot.activeElement) {
            element = element.shadowRoot.activeElement;
        }
        return element;
    }
    function keepVisible() {
        var element = focused();
        if (!element || !(element.isContentEditable || element.tagName === "TEXTAREA" ||
            (element.tagName === "INPUT" && /^(text|search|email|url|tel|number|password)$/i.test(element.type)))) return;
        var viewport = window.visualViewport;
        var top = viewport ? viewport.offsetTop : 0;
        var bottom = top + (viewport ? viewport.height : window.innerHeight);
        var box = element.getBoundingClientRect();
        if (box.top < top + 16 || box.bottom > bottom - 16) {
            // Scroll the original element; do not copy values or synthesize input.
            // Browser/React input events and Korean IME composition stay native.
            element.scrollIntoView({ block: "center", inline: "nearest", behavior: "instant" });
        }
    }
    function schedule() {
        clearTimeout(pending);
        pending = setTimeout(keepVisible, 120);
    }
    window.addEventListener("resize", schedule, { passive: true });
    window.addEventListener("orientationchange", schedule, { passive: true });
    document.addEventListener("focusin", schedule);
    if (window.visualViewport) window.visualViewport.addEventListener("resize", schedule, { passive: true });
}());
