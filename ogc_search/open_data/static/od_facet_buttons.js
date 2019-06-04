$(function(){
// reset seessionStorage based on the URL
    sessionStorage.clear();
    let facets = [];
    if (window.location.search.length > 1) {
        facets = window.location.search.substring(1).split('&');
        for (let i=0; i<facets.length; i++) {
            let pair = facets[i].split('=');
            sessionStorage.setItem(pair[0], pair[1]);
            if (pair[0].substring(0,3).match(/^(\D\D-)$/)) {
                let display_terms = decodeURIComponent(pair[1]).split('|');
                for(let j=0; j<display_terms.length; j++) {
                   let display_key = pair[0];
                    let new_link = $("<a />", {
                        class: "btn btn-default btn-xs",
                        onclick: `select_facet('${display_terms[j]}','${display_key}');`,
                        text: `${display_terms[j]} `
                    }).append($("<span />", {class: 'glyphicon glyphicon-remove', text: ' '}));
                    $('#search_terms').append(new_link);
                }
            }
        }
    }
});