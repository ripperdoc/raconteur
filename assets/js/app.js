// IMPORTANT. This sets the STATIC_PATH to that of the server, in a global var (_page.html).
__webpack_public_path__ = STATIC_URL.replace('replace', '');

// Needed for all pages, and should be loaded first
var jQuery = require('jquery');
window.$ = window.jQuery = jQuery;  // Set global access to jquery object

var svgs = require.context("../gfx/", false, /\.svg$/)
svgs.keys().forEach(svgs); // Requires all files individually to call the sprite

// Load early in case of error below
if (ROLLBAR_CONFIG) {
    var Rollbar = require('rollbar-browser').init(ROLLBAR_CONFIG);
}


// Own plugins
var utils = require('utils');
// require('editablelist.js'); // currently not used
// require('autosave.js')


// Styles. Always load for simplicity.
require('bootstrap/dist/css/bootstrap.css')
require('selectize/dist/css/selectize.bootstrap3.css');
require('flatpickr/dist/flatpickr.min.css');
require('trumbowyg/dist/ui/trumbowyg.css');
require('../css/app.css');


/* ========================================================================
 * Event management (Dependencies: jQuery and utils)
 * ========================================================================
 */

// Globally availale functions
window.set_aspect = function (img) {
    var aspect = img.width / img.height;
    $(img).closest('.gallery-item').css({'width': 100 * aspect / 4.0 + '%', 'flex-grow': aspect})
}

$('#themodal').on('show.bs.modal', function (event) {
    if (event.relatedTarget && event.relatedTarget.href) {
        var $modal = $(this)
        // This is hack, normally remote would be populated but when launched manually from trumbowyg it isn't
        //$modal.data('bs.modal').options.remote = event.relatedTarget.href;
        utils.load_content(event.relatedTarget.href, $modal.find('.modal-content'));
    }
    $(document).one('hide.bs.modal', '#themodal', function (e) {
        // We notify the originating button that modal was closed
        $(event.relatedTarget).trigger('hide.bs.modal.atbtn')
    });
});

// Catches clicks on the modal submit button and submits the form using AJAX
var $modal = $('#themodal')
$modal.on('click', 'button[type="submit"]', function (e) {
    var form = $modal.find('form')[0]
    if (form && form.action) {
        e.preventDefault()
        var jqxhr = $.post(form.action, $(form).serialize())
            .done(function (data, textStatus, jqXHR) {
                console.log(data)
                $modal.modal('hide')
            })
            .fail(function (jqXHR, textStatus, errorThrown) {
                utils.flash_error(jqXHR.responseText, 'danger', $modal.find('#alerts'))
            })
    } else {
        $modal.modal('hide')
    }
});


$(document).on('click', '.buy-link', function (e) {
    var jqxhr = $.ajax({
        url: SHOP_URL,
        type: 'patch',
        data: {product: this.id},
        headers: {'X-CSRFToken': CSRF_TOKEN},
        dataType: 'json',
        success: function (data) {
            $c = $('#cart-counter')
            $c.find('.badge').html(data.instance.total_items)
            $c.addClass("bounce").one('animationend webkitAnimationEnd oAnimationEnd', function () {
                $c.removeClass("bounce");
            });
            $c.addClass("highlight")
        }
    })
        .fail(function (jqXHR, textStatus, errorThrown) {
            utils.flash_error(jqXHR.responseText)
        });
    e.preventDefault();
});

$(document).on('click', '.content-editor a', function (e) {
    return false; // Ignore clicks on links in editor so we dont leave page
});

$(document).on('click', '#themodal a', function (e) {
    var $a = $(this), target = $a.attr('target'), $thm = $('#themodal')
    if (target !== '_blank') {
        utils.load_content($a.attr('href'), target || $thm.find('.modal-content'), $thm.data('bs.modal').options.remote);
        return false
    } // else do nothing special
});

// Loads HTML fragment data into a container when a link is pressed
$(document).on('click', '.loadlink', function (e) {
    var $a = $(this), $parent = $a.parent()
    utils.load_content($a.attr('href'), $parent, null, true);
    $a.remove()
    return false;
});

// Send feedback to Slack
$('#feedback-modal').on('submit', 'form', function (e) {
    var input = $(this).serializeArray()
    var type = input[0]['value'] || 'error'
    var desc = input[1]['value'] || 'none'
    var user = input[2]['value'] || 'Anonymous'
    var payload = {
        'attachments': [
            {
                "fallback": "Received " + type + ": " + desc,
                "pretext": "Received " + type + " for " + window.location,
                "text": desc,
                "author_name": user,
                "author_link": user.indexOf("@") > 0 ? "mailto:" + user : '',
                "color": type == 'error' ? "danger" : "warning"
            }
        ]
    }
    ga('send', 'event', type, '(selector)', desc);
    $.post(
        'https://hooks.slack.com/services/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',
        JSON.stringify(payload))
    e.preventDefault()
    $('#feedback-modal').modal('hide')
});

$(document).on('click', '.selectable', function (e) {
    var $target = $(this), sel = parseInt($target.attr('data-selection'));
    var $parent = $target.parent(), multi = $parent.data('selectmultiple');
    if (!multi) {
        // If single select, always remove all other selections
        $parent.find('[data-selection]').each(function (i, el) {
            $(el).removeAttr('data-selection')
        })
    }
    if (sel > 0) {
        $target.removeAttr('data-selection') // Remove old selection
        var $selected = $parent.find('[data-selection]');
        $selected.each(function (i, el) {
            var $el = $(el);
            var n = parseInt($el.attr('data-selection'));
            if (n > sel)
                $el.attr('data-selection', n - 1)

        });
    } else {
        var total = $parent.find('[data-selection]').length;
        $target.attr('data-selection', total + 1) // Add new selection with last index
        // No need to update previous selections
    }
});

$(document).on('click', '.zoomable', function (e) {
    var $el = $(this), $img = $el.find('img')
    var screenAspect = document.documentElement.clientWidth / document.documentElement.clientHeight;
    var img_aspect = $img.width() / $img.height()
    $el.toggleClass('zoomed')
    if (img_aspect > screenAspect) { // wider than screen
        $img.toggleClass('fill-width')
    } else {
        $img.toggleClass('fill-height')
    }
    return false;
});

/* ========================================================================
 * All events that should run on DOM first ready and at update.
 * ========================================================================
 */
function init_dom(e) {
    // e will be the jquery object if called at DOMLoaded, otherwise the e.target is the node that triggered
    var scope = e===$ ? $(document) : $(e.target)

    // Bootstrap plugins
    // Loads themselves. Load at all pages!
    require('bootstrap/js/dropdown');
    require('bootstrap/js/modal');
    require('bootstrap/js/alert');
    require('bootstrap/js/collapse');
    require('bootstrap/js/button');

    // Bootstrap tooltip
    require('bootstrap/js/tooltip');
    scope.find("a[data-toggle='tooltip']").tooltip(); // Need to activate manually


    // Selectize plugin for SELECTS in forms
    require('selectize');

    scope.find('.selectize').selectize()
    scope.find('.selectize-tags').selectize({
        delimiter: ',',
        persist: false,
        create: function (input) {
            return {
                value: input,
                text: input
            }
        }
    });
    scope.find('.selectize').on('selectize:unselect', function (e) {
        // TODO this is a hack to select the __None item, residing at index 0, to correctly empty the field
        if (e.currentTarget.selectedIndex == -1) {
            e.currentTarget.selectedIndex = 0;
        }
    })

    // Flatpickr for date-felds in forms
    var flatpickr = require('flatpickr');
    $('.flatpickr-datetime').flatpickr({
        "enableTime": true,
        "mode": "single",
        "enableSeconds": true,
        "time_24hr": true,
        "allowInput": true
    })

    // Autosize plugin
    var autosize = require('autosize')
    autosize($('textarea')); // Activate on textareas

    // File upload plugin for file upload forms
    require('fileuploader.js')
    scope.find('.file-upload').fileupload({static_url: STATIC_URL});

    // File select plugin (activates the jquery part, the trumbowyg part loads with trumbowyg later)
    require('fileselect.js')
    scope.find('.fileselect').fileselect({image_url: IMAGE_URL, image_select_url: IMAGE_SELECT_URL});

    // Calculatable plugin
    require('calculatable.js')
    scope.find('.calc[data-formula]').calculatable();


    scope.find('.content-editor').each(function (e) {
        // Loads these dependencies asynchrounously if we find this scope on the current page
        require.ensure(['trumbowyg', 'fileselect.js', 'trumbowyg.fileselect.js', 'trumbowyg.markdown.js'], function (require) {
            // Trumbowyg plugin for textareas
            require('trumbowyg')
            require('trumbowyg.fileselect.js')  // File select trumbo plugin
            require('trumbowyg.markdown.js')  // Markdown coversion to underlying textarea

            // Set path to SVG, will be fetched by trumbowyg using XHR
            $.trumbowyg.svgPath = require('trumbowyg/dist/ui/icons.svg')
            var $textarea = $('.content-editor')
            var options = {}
            $.each($('#images').find('option'), function (i, el) {
                options[el.text.trim()] = el.value;
            })
            $textarea.trumbowyg({
                btns: ['strong', 'em', '|', 'formatting', 'unorderedList', 'orderedList', 'link',
                    ['fileselect', 'wide', 'center', 'portrait'], 'viewHTML', 'fullscreen'],
                autogrow: true,
                removeformatPasted: true,
                image_select_url: IMAGE_SELECT_URL
            })
        });

    })



}

// function update_gallery(e) {
//     // No dependency
//     var list = $(e.target).find('.gallery').addBack('.gallery'); // addBack adds the $(e.target) if it also matches .gallery
//     $.each(list, function (i, el) {
//         var $el = $(el), max_aspect = $el.data('maxaspect') || 3.0, items = $el.find('.gallery-item'), sumaspect = 0.0,
//             row = [], aspect;
//         items.each(function (i, item) {
//             item = $(item)
//             row.push(item)
//             aspect = parseFloat(item.data('aspect')) || 1.0;
//             sumaspect += aspect;
//             if (sumaspect > max_aspect || i == items.length - 1) {
//                 $.each(row, function (i, item) {
//                     var w = (100 - row.length) * (parseFloat(item.data('aspect')) || 1.0) / sumaspect;
//                     item.css('width', w + "%")
//                 });
//                 // set width for all in row
//                 row = [];
//                 sumaspect = 0.0
//             }
//         })
//     })
// }

$(init_dom)
$(document).on('fablr.dom-updated', init_dom);
