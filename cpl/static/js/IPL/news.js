$(document).on("click", "#loadmorebtn", function () {
    $('.loader-main').show();
    var page = $('#loadmorebtn').attr('data-page'); 
    $.ajax({
        url: "/newslistshow",
        type: "GET",
        // data: { "tab": tab , 'page':page },
        data: {'page':page },
        headers: {
            'X-CSRF-TOKEN': $('meta[name="csrf-token"]').attr('content')
        },
        dataType: 'JSON',
        success: function (response) {

            if (response.status == true) {
                $('.loader-main').hide();
                // $('#bannerDiv').html(response.banner);
                $('#newsData').append(response.news_data);
                $('#loadmorebtn').attr('data-page',parseInt(response.newsResponce.page) + 1);
            }
        },
        error: function (response) {
        }
    });
});

$(document).on("click", "#loadmorebtnTeam", function () {
    $('.loader-main').show();
    var page = $('#loadmorebtnTeam').attr('data-page'); 
    var id = $('#loadmorebtnTeam').attr('data-id'); 
    var type = $('#loadmorebtnTeam').attr('data-type');
    $.ajax({
        url: "/newslistshowTeam",
        type: "GET",
        // data: { "tab": tab , 'page':page },
        data: {
            'page':page,
            'id':id,
            'type':type
        },
        headers: {
            'X-CSRF-TOKEN': $('meta[name="csrf-token"]').attr('content')
        },
        dataType: 'JSON',
        success: function (response) {

            if (response.status == true) {
                
                // $('#bannerDiv').html(response.banner);
                $('.loader-main').hide();
                $('#newsData').append(response.news_data);
                $('#loadmorebtnTeam').attr('data-page',parseInt(page) + 1);
                var totalPageno = (((response.newsResponce.total/page)) / 21);
                if (totalPageno == page || totalPageno < 1) {
                    $('.loadmorebtn').hide();
                } else {
                    $('.loadmorebtn').show();
                }
            }else{
                $('.loader-main').hide();
                $('.loadmorebtn').hide();
            }
        },
        error: function (response) {
        }
    });
});


$(document).on("click", "#loadMoreaddBtn", function () {
    $('.loader-main').show();
    var page = $('#loadMoreaddBtn').attr('data-page'); 
    var type = $('#loadMoreaddBtn').attr('data-type'); 
    var year=$('#yeardropdown').find(":selected").val();
    var slug = $('#teamsdropdown').find(":selected").val();
    var team = $('#loadMoreaddBtn').attr('data-type'); 
    page = parseInt(page);
    $.ajax({
        url: "/add-more-match-report",
        type: "GET",
        data: {'page':page, "type":type, 'year':year ,'slug':slug},
        headers: {
            'X-CSRF-TOKEN': $('meta[name="csrf-token"]').attr('content')
        },
        dataType: 'JSON',
        success: function (response) {
            if (response.status == true) {
                 var totalPageno = Math.ceil(parseFloat(response.newsResponce.total / 21));
                // if (totalPageno == response.newsResponce.page || totalPageno == 0) {
                if (totalPageno == page || totalPageno == 0) {
                    $('.loadmorebtn').hide();   
                } else {
                    $('.loadmorebtn').show();
                }
                $('.loader-main').hide();
                // $('#bannerDiv').html(response.banner);
                $('#div-match-report').append(response.news_data);
                $('#loadMoreaddBtn').attr('data-page', page + 1);
            }
        },
        error: function (response) {
        }
    });
});


$(document).on("change", "#yeardropdown,#teamsdropdown", function() {
    $('.loadmorebtn').hide();
    var page = 1; 
    var type = $('#loadMoreaddBtn').attr('data-type'); 
    var year=$('#yeardropdown').find(":selected").val();
    // var team = $('#teamsdropdown').find(":selected").val();
    var team=$('#teamsdropdown').val();
    var slug = $('#page-slug').val(); 
    page = parseInt(page);
    $('#div-match-report').html('');
    $.ajax({
        url: "/filter-add-more-match-report",
        type: "GET",
        data: {'page':page, "type":type, 'year':year ,'slug':slug, 'team_slug':team},
        headers: {
            'X-CSRF-TOKEN': $('meta[name="csrf-token"]').attr('content')
        },
        dataType: 'JSON',
        success: function (response) {
            if (response.status == true) {
                $('.loadmorebtn').hide();
                $('#main-page').html(response.news_data);
                $('#loadMoreaddBtn').attr('data-page', page + 1);
                $('#teamsdropdown').val(response.team);
            
                if(response.total_results > 1){
                    if ($('.ap-slider-video').length > 0) {
                        $('.ap-slider-video').slick({
                            slidesToShow: 1,
                            slidesToScroll: 1,
                            arrows: !0,
                            dots: !0,
                            fade: !0,
                            speed: 500,
                            autoplay: !0,
                            autoplaySpeed: 4e3,
                            adaptiveHeight: !0,
                            lazyLoad: "ondemand",
                            appendDots: $(".slide-m-dots"),
                            prevArrow: $(".slide-m-prev"),
                            nextArrow: $(".slide-m-next"),
                        });
                        $('.ap-slider-video').show();
                    }
                } else {
                    $(window).scrollTop(0);
                    $('.ap-slider-video').slick({
                        slidesToShow: 1,
                        slidesToScroll: 1,
                        arrows: !0,
                        dots: !0,
                        fade: !0,
                        speed: 500,
                        autoplay:false,
                        autoplaySpeed: 4e3,
                        adaptiveHeight: !0,
                        lazyLoad: "ondemand",
                        appendDots:false,
                        prevArrow: false,
                        nextArrow: false,
                    });
                    $('.ap-slider-video').show();
                }
            
                $('.loadmorebtn').show();
            } else {
                $('.loadmorebtn').hide();
                $('#loadMoreaddBtn').hide();
                $('.Datanotfound').show();
                $('.hideSliderDiv').hide();
            }
            
        },
        error: function (response) {
        }
    });
   
});