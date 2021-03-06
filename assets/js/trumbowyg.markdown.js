/**
 * Created by martin on 2016-10-20.
 */

define(["jquery", "utils", "turndown", "marked"], function ($, utils, turndown_dep, marked) {
    $.extend(true, $.trumbowyg, {
        plugins: {
            markdown: {
                // shouldInit: isSupported,
                init: function (trumbowyg) {
                    var turndownService = new turndown_dep.default(); // use default because ES module
                    turndownService.keep(['table', 'tr', 'td', 'th', 'thead', 'tbody', 'tfoot'])
                    // Patches the val() function of the $ta that represents the jqueryied textarea, so that it
                    // converts html->markdown when set, and markdown->html when read.

                    var oldval = trumbowyg.$ta.val
                    trumbowyg.$ta.val = function (value) {
                        // console.log(value)
                        if (typeof value == 'undefined') {
                            // Act as a getter
                            var rv = oldval.call(trumbowyg.$ta);
                            var renderer = new marked.Renderer();
                            // Render special gallery lists into a gallery
                            renderer.list = function (body, ordered) {
                                if (!ordered && /^<li>gallery-(center|wide|side)/.test(body)) {
                                    body = body.replace(/^<li>(gallery-(center|wide|side))/, '<ul contenteditable="false" class="gallery $1"><li class="hide">$1') + '</ul>'
                                    body = body.replace(/<li>/g, '<li class="gallery-item">')
                                }
                                return body
                            }
                            return marked(rv, {renderer: renderer})
                        }
                        var markdown = turndownService.turndown(value);
                        oldval.call(trumbowyg.$ta, markdown);
                    };
                }
            }
        }
    });
});