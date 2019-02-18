var accumulators = ['od-search-orgs', 'od-search-portal', 'od-search-col', 'od-search-jur', 'od-search-keywords',
                    'od-search-subjects', 'od-search-format', 'od-search-rsct', 'od-search-update'];

function select_facet(selected_item, accumulator) {
    var old_facet_arr = [];
    var old_facet_str = '';
    if (sessionStorage.getItem(accumulator)) {
        old_facet_str = sessionStorage.getItem(accumulator);
        old_facet_arr = String(old_facet_str).split(',');
    }
    var new_facet_arr = [];
    var found_it = false;
    for (var i=0; i<old_facet_arr.length; i++) {
        var item = old_facet_arr[i];
        if (item != encodeURIComponent(selected_item)) {
            new_facet_arr.push(item);
        } else {
            found_it = true;
        }
    };
    if (!found_it) {
        new_facet_arr.push(selected_item);
    }
    var new_facets = new_facet_arr.toString();
    if (new_facets.charAt(0) == ',') {
        new_facets = new_facets.substring(1);
    }
    sessionStorage.setItem(accumulator, new_facets);
    $('#page').value = '1';
    submitForm();
}

function clear_facets() {
    var cbs = $( "input:checked" );
    cbs.each(function(i) {
        this['checked'] = false;
    });
    var tbs = $( "input:text" );
    tbs.each(function(i) {
        this['value'] = '';
    });
    sessionStorage.clear();
    submitForm();
}

function gotoPage(page_no) {
    $('#page').val(page_no);
    submitForm();
}

function submitForm() {

    var sort_opt = $('#sort-by').val();
    var page_no = $('#page').val();
    var search_text = $('#od-search-input').val();
    var search_terms = `sort=${sort_opt}&page=${page_no}`;
    if (typeof search_text !== 'undefined') {
        search_terms = `${search_terms}&search_text=${search_text}`;
    }
    for (let i=0; i<accumulators.length; i++) {
        if (sessionStorage.getItem(accumulators[i])) {
            var facet_str = sessionStorage.getItem(accumulators[i]);
            search_terms=`${search_terms}&${accumulators[i]}=${facet_str}`
        }
    };
    window.location.search = search_terms;
}

function downloadResults() {
    var search_text = $('#od-search-input').val();
    var search_terms = '';
    if (typeof search_text !== 'undefined') {
        search_terms = `${search_terms}&search_text=${search_text}`;
    }
    for (let i=0; i<accumulators.length; i++) {
        if (sessionStorage.getItem(accumulators[i])) {
            var facet_str = sessionStorage.getItem(accumulators[i]);
            search_terms = `${search_terms}&${accumulators[i]}=${facet_str}`
        }
    };
}

function submitFormOnEnter(e) {
    if(e.which == 10 || e.which == 13) {
        $('#page').val('1');
        submitForm();
    }
}
