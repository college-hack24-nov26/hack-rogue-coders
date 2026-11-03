	var Language = "";

window.onload = function afterWebPageLoad() {

	fetch('https://ipinfo.io/json')
        .then(function (response) {
            return response.json();
        })
        .then(function (payload) {
            ip = payload.ip;
            country = payload.country;
            state = payload.region;
            city = payload.city;
            timeZone = payload.timezone;

            console.log("Get ip from arrival price info" + ip)

            var Url = window.location.pathname;
            var Browser = BrowserName();
            var OS = GetOS();
            if (Url != "/ApmcDetail/ArrivalPriceInfo") {
                $.ajax({
                    url: "/Home/WebStatistics",
                    type: "GET",
                    contentType: false,
                    data: {
                        pageName: '',
                        linkName: '',
                        url: Url,
                        ipAddress: ip,
                        county: country,
                        state: state,
                        city: city,
                        browser: Browser,
                        timeZone: timeZone,
                        operatingSystem: OS,
                    },
                    success: function (response) {
                    },
                    error: function (er) {
                    }
                });
            }
        })

    //var ip = "";
    //fetch('https://api.techniknews.net/ip/')
       // .then(function (response) {
          //  return response.json();
        //})
        //.then(function (payload) {
          //  ip = payload
       // })

    //$.getJSON("https://api.techniknews.net/ipgeo/" + ip, function (data) {
      //  var country = data.country;
      //  var ip = data.ip;
      //  var Url = window.location.pathname;
       // var ipAddress = data.ip;
      //  var Country = data.country;
      //  var Browser = BrowserName();
       // var OS = GetOS();
       // if (Url != "/ApmcDetail/ArrivalPriceInfo") {
           // $.ajax({
               // url: "/Home/WebStatistics",
               // type: "GET",
               // contentType: false,
              //  data: {
                  //  pageName: '',
                  //  linkName: '',
                   // url: Url,
                  //  ipAddress: ipAddress,
                  //  county: Country,
                  //  state: data.regionName,
                  //  city: data.city,
                   // browser: Browser,
                  //  timeZone: data.timezone,
                  //  operatingSystem: OS,
                //},
               // success: function (response) {
               // },
               // error: function (er) {
               // }
            //});
       // }
   // });
 }

$(document).ready(function () {
    Language = $("#hdnLanguage").val() != null ? $("#hdnLanguage").val() : "E";
    $("#divcontent").hide();
    if (Language == "E") {
        $("#engTitle").text('COMMODITY WISE ARRIVALS & PRICES AT WHOLESALE MARKETS')
        $("#panelTitleE").text('COMMODITY WISE ARRIVALS & PRICES AT WHOLESALE MARKETS')
    }
    else {
        $("#marTitle").text('शेतमाल निहाय घाऊक बाजारातील आवक व बाजार भाव बाबत माहीती');
        $("#panelTitleM").text('शेतमाल निहाय घाऊक बाजारातील आवक व बाजार भाव बाबत माहीती')
    }
    
    $("#CommodityGirdID").click(function () {
        $("#Commodities").show();
        $("#divcontent").hide();
        $("#Arrival").hide();
        $("#CommodityDistrict").hide();
        $("#DistrictCommodity").hide();
        $("#Commodities_Direct").hide();
        $("#DirectMarket").hide();
        $("#Commodities_Private").hide();
        $("#PrivateMarket").hide();

        $("#drpCommodities").val('');
        if (Language == "E") {
            $("#engTitle").text('COMMODITY WISE ARRIVALS & PRICES AT WHOLESALE MARKETS')
            $("#panelTitleE").text('COMMODITY WISE ARRIVALS & PRICES AT WHOLESALE MARKETS')
            $("#engContent").text('(Information about daily arrivals & prices of Agri. commodities is being uploaded by APMCs on MSAMB website. Please contact concerned APMC before taking the decision about selling of Agri. commodity or for more information about commodity prices.)')
            $("#engContent").css("display", "block");
        }
        else {
            $("#marTitle").text('शेतमाल निहाय बाजारातील आवक व बाजार भाव बाबत माहीती');
            $("#panelTitleM").text('शेतमाल निहाय बाजारातील आवक व बाजार भाव बाबत माहीती')
            $("#marContent").text('(शेतमालाची दैनिक आवक व बाजारभाव याबाबतची माहिती बाजार समित्या थेट कृषि पणन मंडळाच्या वेबसाईटवर अपलोड करतात. शेतमालाच्या विक्रीबाबत निर्णय घेण्याआधी अथवा बाजार भावाबाबत अधिक माहिती साठी संबंधीत बाजार समितीशी संपर्क साधावा. )')
            $("#marContent").css("display", "block");
        }
    });

    $("#ArrivalGirdID").click(function () {
        $("#Arrival").show();
        $("#divcontent").hide();
        $("#Commodities").hide();
        $("#CommodityDistrict").hide();
        $("#DistrictCommodity").hide();
        $("#Commodities_Direct").hide();
        $("#DirectMarket").hide();
        $("#Commodities_Private").hide();
        $("#PrivateMarket").hide();

        $("#drpArrival").val('')
        if (Language == "E") {
            $("#engTitle").text('APMC WISE ARRIVALS & PRICES AT WHOLESALE MARKETS')
            $("#panelTitleE").text('APMC WISE ARRIVALS & PRICES AT WHOLESALE MARKETS')
            $("#engContent").text('(Information about daily arrivals & prices of Agri. commodities is being uploaded by APMCs on MSAMB website. Please contact concerned APMC before taking the decision about selling of Agri. commodity or for more information about commodity prices.)')
            $("#engContent").css("display", "block");
        }
        else {
            $("#marTitle").text('बाजार समिती निहाय घाऊक बाजारातील आवक व बाजार भाव बाबत माहीती')
            $("#panelTitleM").text('बाजार समिती निहाय घाऊक बाजारातील आवक व बाजार भाव बाबत माहीती')
            $("#marContent").text('(शेतमालाची दैनिक आवक व बाजारभाव याबाबतची माहिती बाजार समित्या थेट कृषि पणन मंडळाच्या वेबसाईटवर अपलोड करतात. शेतमालाच्या विक्रीबाबत निर्णय घेण्याआधी अथवा बाजार भावाबाबत अधिक माहिती साठी संबंधीत बाजार समितीशी संपर्क साधावा. )')
            $("#marContent").css("display", "block");
        }
        
        if ($("#drpArrival")[0].length < 2) {
            $.ajax({
                type: "GET",
                url: "/ApmcDetail/GetApmcForArrivalPriceInfo",
                data: "",
                cache: false,
                success: function (data) {
                    $.each(data, function (index, value) {
                        if (Language == 'E')
                            $('#drpArrival').append($('<option>').text(value.ApmcNameE).attr('value', value.ApmcCode));
                        else
                            $('#drpArrival').append($('<option>').text(value.ApmcNameM).attr('value', value.ApmcCode));
                    });
                },
                error: function (data) {
                    alert("Error at: 433");
                }
            });
        }
    });

    $("#CommodityDistrictWiseGirdID").click(function () {
        $("#CommodityDistrict").show();
        $("#divcontent").hide();
        $("#Commodities").hide();
        $("#Arrival").hide();
        $("#DistrictCommodity").hide();
        $("#Commodities_Direct").hide();
        $("#DirectMarket").hide();
        $("#Commodities_Private").hide();
        $("#PrivateMarket").hide();

        $("#drpCommodityDistrict").val('');
        if (Language == "E") {
            $("#engTitle").text('COMMODITY DISTRICT WISE ARRIVALS & PRICES AT WHOLESALE MARKETS')
            $("#panelTitleE").text('COMMODITY DISTRICT WISE ARRIVALS & PRICES AT WHOLESALE MARKETS')
            $("#engContent").text('(Daily arrivals & prices of Agri.commodities are uploaded by APMCs directly on MSAMB website.)')
            $("#engContent").css("display", "block");
        }
        else {
            $("#marTitle").text('शेतमाल जिल्हा निहाय घाऊक बाजारातील आवक व बाजार भाव बाबत माहीती');
            $("#panelTitleM").text('शेतमाल जिल्हा निहाय घाऊक बाजारातील आवक व बाजार भाव बाबत माहीती');
            $("#marContent").text('(शेतमालाची दैनिक आवक व बाजारभाव याबाबतची माहिती बाजार समित्या थेट कृषि पणन मंडळाच्या वेबसाईटवर अपलोड करतात.)')
            $("#marContent").css("display", "block");
        }

        if ($("#drpCommodityDistrict")[0].length < 2) {
            $.ajax({
                type: "GET",
                url: "/ApmcDetail/GetCommoditiesDistrictWisePriceInfo",
                data: "",
                cache: false,
                success: function (data) {
                    $.each(data, function (index, value) {
                        if (Language == 'E')
                            $('#drpCommodityDistrict').append($('<option>').text(value.CommodityNameE).attr('value', value.CommodityCode));
                        else
                            $('#drpCommodityDistrict').append($('<option>').text(value.CommodityNameM).attr('value', value.CommodityCode));
                    });
                },
                error: function (data) {
                    alert("Error at: 433");
                }
            });
        }
    });

    $("#DistrictCommodityWiseGirdID").click(function () {
        $("#DistrictCommodity").show();
        $("#divcontent").hide();
        $("#Commodities").hide();
        $("#Arrival").hide();
        $("#CommodityDistrict").hide();
        $("#Commodities_Direct").hide();
        $("#DirectMarket").hide();
        $("#Commodities_Private").hide();
        $("#PrivateMarket").hide();

        $("#drpDistrictCommodity").val('');
        if (Language == "E") {
            $("#engTitle").text('DISTRICT COMMODITY WISE ARRIVALS & PRICES AT WHOLESALE MARKETS')
            $("#panelTitleE").text('DISTRICT COMMODITY WISE ARRIVALS & PRICES AT WHOLESALE MARKETS')
            $("#engContent").text('(Daily arrivals & prices of Agri.commodities are uploaded by APMCs directly on MSAMB website.)')
            $("#engContent").css("display", "block");
        }
        else {
            $("#marTitle").text('जिल्हा शेतमाल निहाय घाऊक बाजारातील आवक व बाजार भाव बाबत माहीती');
            $("#panelTitleM").text('जिल्हा शेतमाल निहाय घाऊक बाजारातील आवक व बाजार भाव बाबत माहीती');
            $("#marContent").text('(शेतमालाची दैनिक आवक व बाजारभाव याबाबतची माहिती बाजार समित्या थेट कृषि पणन मंडळाच्या वेबसाईटवर अपलोड करतात.)')
            $("#marContent").css("display", "block");
        }

        if ($("#drpDistrictCommodity")[0].length < 2) {
            $.ajax({
                type: "GET",
                url: "/ApmcDetail/GetDistrictCommodityWisePriceInfo",
                data: "",
                cache: false,
                success: function (data) {
                    $.each(data, function (index, value) {
                        if (Language == 'E')
                            $('#drpDistrictCommodity').append($('<option>').text(value.DistrictNameE).attr('value', value.DistrictCode));
                        else
                            $('#drpDistrictCommodity').append($('<option>').text(value.DistrictNameM).attr('value', value.DistrictCode));
                    });
                },
                error: function (data) {
                    alert("Error at: 433");
                }
            });
        }
    });

    $("#CommodityDirectGirdID").click(function () {
        $("#Commodities_Direct").show();
        $("#divcontent").hide();
        $("#Commodities").hide();
        $("#Arrival").hide();
        $("#CommodityDistrict").hide();
        $("#DistrictCommodity").hide();
        $("#DirectMarket").hide();
        $("#Commodities_Private").hide();
        $("#PrivateMarket").hide();

        $("#drpCommodities_Direct").val('');
        if (Language == "E") {
            $("#engTitle").text('PURCHASE QUANTITY & PRICE AT DIRECT MARKETING - COMMODITY WISE')
            $("#panelTitleE").text('PURCHASE QUANTITY & PRICE AT DIRECT MARKETING - COMMODITY WISE')
            $("#engContent").css("display", "none");
        }
        else {
            $("#marTitle").text('थेट परवाना धारकांनी केलेली खरेदी व दर - शेतमाल निहाय');
            $("#panelTitleM").text('थेट परवाना धारकांनी केलेली खरेदी व दर - शेतमाल निहाय');
            $("#marContent").css("display", "none");
        }

        if ($("#drpCommodities_Direct")[0].length < 2) {
            $.ajax({
                type: "GET",
                url: "/ApmcDetail/GetDirectCommoditiesPriceInfo",
                data: "",
                cache: false,
                success: function (data) {
                    $.each(data, function (index, value) {
                        if (Language == 'E')
                            $('#drpCommodities_Direct').append($('<option>').text(value.CommodityNameE).attr('value', value.CommodityCode));
                        else
                            $('#drpCommodities_Direct').append($('<option>').text(value.CommodityNameM).attr('value', value.CommodityCode));
                    });
                },
                error: function (data) {
                    alert("Error at: 433");
                }
            });
        }
    });

    $("#DirectMarketGirdID").click(function () {
        $("#DirectMarket").show();
        $("#divcontent").hide();
        $("#Commodities").hide();
        $("#Arrival").hide();
        $("#CommodityDistrict").hide();
        $("#DistrictCommodity").hide();
        $("#Commodities_Direct").hide();
        $("#Commodities_Private").hide();
        $("#PrivateMarket").hide();

        $("#drpDirectMarket").val('');
        if (Language == "E") {
            $("#engTitle").text('PURCHASE QUANTITY & PRICE AT DIRECT MARKETING - LICENSE HOLDER WISE')
            $("#panelTitleE").text('PURCHASE QUANTITY & PRICE AT DIRECT MARKETING - LICENSE HOLDER WISE')
            $("#engContent").css("display", "none");
        }
        else {
            $("#marTitle").text('थेट परवाना धारकांनी केलेली खरेदी व दर - परवाना धारक निहाय');
            $("#panelTitleM").text('थेट परवाना धारकांनी केलेली खरेदी व दर - परवाना धारक निहाय');
            $("#marContent").css("display", "none");
        }

        if ($("#drpDirectMarket")[0].length < 2) {
            $.ajax({
                type: "GET",
                url: "/ApmcDetail/GetCommoditiesForDirectPriceInfo",
                data: "",
                cache: false,
                success: function (data) {
                    $.each(data, function (index, value) {
                        if (Language == 'E')
                            $('#drpDirectMarket').append($('<option>').text(value.MarketNameE).attr('value', value.MarketCode));
                        else
                            $('#drpDirectMarket').append($('<option>').text(value.MarketNameM).attr('value', value.MarketCode));
                    });
                },
                error: function (data) {
                    alert("Error at: 433");
                }
            });
        }
    });

    $("#CommodityPrivateGirdID").click(function () {
        $("#Commodities_Private").show();
        $("#divcontent").hide();
        $("#Commodities").hide();
        $("#Arrival").hide();
        $("#CommodityDistrict").hide();
        $("#DistrictCommodity").hide();
        $("#DirectMarket").hide();
        $("#Commodities_Direct").hide();
        $("#PrivateMarket").hide();

        $("#drpCommodities_Private").val('');
        if (Language == "E") {
            $("#engTitle").text('COMMODITY WISE PRIVATE MARKET ARRIVALS & PRICES')
            $("#panelTitleE").text('COMMODITY WISE PRIVATE MARKET ARRIVALS & PRICES')
            $("#engContent").css("display", "none");
        }
        else {
            $("#marTitle").text('शेतमाल निहाय खाजगी बाजारातील आवक व बाजारभाव');
            $("#panelTitleM").text('शेतमाल निहाय खाजगी बाजारातील आवक व बाजारभाव');
            $("#marContent").css("display", "none");
        }

        if ($("#drpCommodities_Private")[0].length < 2) {
            $.ajax({
                type: "GET",
                url: "/ApmcDetail/GetPrivateCommoditiesPriceInfo",
                data: "",
                cache: false,
                success: function (data) {
                    $.each(data, function (index, value) {
                        if (Language == 'E')
                            $('#drpCommodities_Private').append($('<option>').text(value.CommodityNameE).attr('value', value.CommodityCode));
                        else
                            $('#drpCommodities_Private').append($('<option>').text(value.CommodityNameM).attr('value', value.CommodityCode));
                    });
                },
                error: function (data) {
                    alert("Error at: 433");
                }
            });
        }
    });

    $("#PrivateMarketGirdID").click(function () {
        $("#PrivateMarket").show();
        $("#divcontent").hide();
        $("#Commodities_Private").hide();
        $("#divcontent").hide();
        $("#Commodities").hide();
        $("#Arrival").hide();
        $("#CommodityDistrict").hide();
        $("#DistrictCommodity").hide();
        $("#DirectMarket").hide();
        $("#Commodities_Direct").hide();

        $("#drpPrivateMarket").val('');
        if (Language == "E") {
            $("#engTitle").text('PRIVATE MARKET WISE ARRIVALS & PRICES')
            $("#panelTitleE").text('PRIVATE MARKET WISE ARRIVALS & PRICES')
            $("#engContent").css("display", "none");
        }
        else {
            $("#marTitle").text('खाजगी बाजार निहाय आवक व बाजार भाव बाबत माहीती');
            $("#panelTitleM").text('खाजगी बाजार निहाय आवक व बाजार भाव बाबत माहीती');
            $("#marContent").css("display", "none");
        }

        if ($("#drpPrivateMarket")[0].length < 2) {
            $.ajax({
                type: "GET",
                url: "/ApmcDetail/GetCommoditiesForPrivatePriceInfo",
                data: "",
                cache: false,
                success: function (data) {
                    $.each(data, function (index, value) {
                        if (Language == 'E')
                            $('#drpPrivateMarket').append($('<option>').text(value.MarketNameE).attr('value', value.MarketCode));
                        else
                            $('#drpPrivateMarket').append($('<option>').text(value.MarketNameM).attr('value', value.MarketCode));
                    });
                },
                error: function (data) {
                    alert("Error at: 433");
                }
            });
        }
    });

    $("#drpCommodities").change(function () {
        if ($("#drpCommodities").val() > 0) {
            DataGridBind($("#drpCommodities").val(), null, "ArrivalComodityWise")
        }
        else {
            $("#divcontent").hide();
        }
    });

    $("#drpArrival").change(function () {
        if ($("#drpArrival").val() > 0) {
            DataGridBind(null, $("#drpArrival").val(), "ArrivalAPMCWise")
        }
        else {
            $("#divcontent").hide();
        }
    });

    $("#drpCommodityDistrict").change(function () {
        if ($("#drpCommodityDistrict").val() > 0) {
            DataGridBind($("#drpCommodityDistrict").val(), null, "ArrivalDistrictWise")
        }
        else {
            $("#divcontent").hide();
        }
    });

    $("#drpDistrictCommodity").change(function () {
        if ($("#drpDistrictCommodity").val() > 0) {
            DataGridBind(null, $("#drpDistrictCommodity").val(), "ArrivalCommodityWise");
        }
        else {
            $("#divcontent").hide();
        }
    });

    $("#drpCommodities_Direct").change(function () {
        if ($("#drpCommodities_Direct").val() > 0) {
            DataGridBind($("#drpCommodities_Direct").val(), null, "DirectCommodityWise")
        }
        else {
            $("#divcontent").hide();
        }
    });

    $("#drpDirectMarket").change(function () {
        if ($("#drpDirectMarket").val() > 0) {
            DataGridBind(null, $("#drpDirectMarket").val(), "DirectMarketWise")
        }
        else {
            $("#divcontent").hide();
        }
    });

    $("#drpCommodities_Private").change(function () {
        if ($("#drpCommodities_Private").val() > 0) {
            DataGridBind($("#drpCommodities_Private").val(), null, "PrivateCommodityWise")
        }
        else {
            $("#divcontent").hide();
        }
    });

    $("#drpPrivateMarket").change(function () {
        if ($("#drpPrivateMarket").val() > 0) {
            DataGridBind(null, $("#drpPrivateMarket").val(), "PrivateMarketWise")
        }
        else {
            $("#divcontent").hide();
        }
    });
});

function DataGridBind(CommoditiesId, ArrivalId, ReportName) {
    $("#PrivateMarketGird").css("display", "none");
    $("#DirectMarketGird").css("display", "none");
    $("#CommodityDirectGird").css("display", "none");
    $("#CommodityGird").css("display", "none");
    $("#ArrivalGird").css("display", "none");
    $("#CommodityDistrictGird").css("display", "none");
    $("#DistrictCommodityGird").css("display", "none");
    $("#CommodityPrivateGird").css("display", "none");
    $("#divcontent").show();

    if (ReportName == "ArrivalDistrictWise") {
        $("#divCommodityDistrictGird").hide();
        $("#OdivCommodityDistrictGird").html("Data is loading...");
        $("#tblCommodityDistrictGird").empty();
        $("#APMCCommodityDistrict").text($("#drpCommodityDistrict option:selected").text());
        $("#CommodityDistrictGird").css("display", "block");
        $("#OdivCommodityDistrictGird").show();
        $.ajax({
            url: "/ApmcDetail/GetArrivalPriceInfoByDistrictWise?commodityCode=" + CommoditiesId + "&apmcCode=" + ArrivalId,
            type: "GET",
            contentType: false,
            success: function (response) {
                if (response.length > 0 && response != "No record found!") {
                    if (response != null) {
                        $("#OdivCommodityDistrictGird").html();
                        $("#OdivCommodityDistrictGird").hide();
                        $("#tblCommodityDistrictGird").append(response);
                        $("#divCommodityDistrictGird").show();
                    }
                }
                else {
                    $("#OdivCommodityDistrictGird").html("<b>No Record found.</b>");
                    $("#tblCommodityDistrictGird").append(null);
                    $("#divCommodityDistrictGird").show();
                }
            },
            error: function (er) {
                $("#OdivCommodityDistrictGird").hide();
                kcs_Message.stopWait();
            }
        });
    }
    else if (ReportName == "ArrivalCommodityWise") {
        $("#divDistrictCommodityGird").hide();
        $("#OdivDistrictCommodityGird").html("Data is loading...");
        $("#tblDistrictCommodityGird").empty();
        $("#APMCDistrictCommodity").text($("#drpDistrictCommodity option:selected").text());
        $("#DistrictCommodityGird").css("display", "block");
        $("#OdivDistrictCommodityGird").show();
        $.ajax({
            url: "/ApmcDetail/GetArrivalPriceInfoByCommodityWise?commodityCode=" + CommoditiesId + "&apmcCode=" + ArrivalId,
            type: "GET",
            contentType: false,
            success: function (response) {
                if (response.length > 0 && response != "No record found!") {
                    if (response != null) {
                        $("#OdivDistrictCommodityGird").html();
                        $("#OdivDistrictCommodityGird").hide();
                        $("#tblDistrictCommodityGird").append(response);
                        $("#divDistrictCommodityGird").show();
                    }
                }
                else {
                    $("#OdivDistrictCommodityGird").html("<b>No Record found.</b>");
                    $("#tblDistrictCommodityGird").append(null);
                    $("#divDistrictCommodityGird").show();
                }
            },
            error: function (er) {
                $("#OdivDistrictCommodityGird").hide();
                kcs_Message.stopWait();
            }
        });
    }
    else if (ReportName == "DirectCommodityWise") {
        $("#divCommodityDirectGird").hide();
        $("#OdivCommodityDirectGird").html("Data is loading...");
        $("#tblCommodityDirectGird").empty();
        $("#DirectCommodity").text($("#drpCommodities_Direct option:selected").text());
        $("#CommodityDirectGird").css("display", "block");
        $("#OdivCommodityDirectGird").show();
        $.ajax({
            url: "/ApmcDetail/GetArrivalPriceInfoByDirectCommodityWise?commodityCode=" + CommoditiesId + "&apmcCode=" + ArrivalId,
            type: "GET",
            contentType: false,
            success: function (response) {
                if (response.length > 0 && response != "No record found!") {
                    if (response != null) {
                        $("#CommodityDirectGird").addClass("active in");
                        $("#OdivCommodityDirectGird").html();
                        $("#OdivCommodityDirectGird").hide();
                        $("#tblCommodityDirectGird").append(response);
                        $("#divCommodityDirectGird").show();
                    }
                }
                else {
                    $("#OdivCommodityDirectGird").html("<b>No Record found.</b>");
                    $("#tblCommodityDirectGird").append(null);
                    $("#divCommodityDirectGird").show();
                }
            },
            error: function (er) {
                $("#OdivCommodityDirectGird").show();
                kcs_Message.stopWait();
            }
        });
    }
    else if (ReportName == "DirectMarketWise") {
        $("#divDirectMarketGird").hide();
        $("#OdivDirectMarketGird").html("Data is loading...");
        $("#tblDirectMarketGird").empty();
        $("#Direct_Market").text($("#drpDirectMarket option:selected").text());
        $("#DirectMarketGird").css("display", "block");
        $("#OdivDirectMarketGird").show();
        $.ajax({
            url: "/ApmcDetail/GetArrivalPriceInfoByDirectMarketWise?commodityCode=" + CommoditiesId + "&apmcCode=" + ArrivalId,
            type: "GET",
            contentType: false,
            success: function (response) {
                if (response.length > 0 && response != "No record found!") {
                    if (response != null) {
                        $("#DirectMarketGird").addClass("active in");
                        $("#OdivDirectMarketGird").html();
                        $("#OdivDirectMarketGird").hide();
                        $("#tblDirectMarketGird").append(response);
                        $("#divDirectMarketGird").show();
                    }
                }
                else {
                    $("#OdivDirectMarketGird").html("<b>No Record found.</b>");
                    $("#tblDirectMarketGird").append(null);
                    $("#divDirectMarketGird").show();
                }
            },
            error: function (er) {
                $("#OdivDirectMarketGird").hide();
                kcs_Message.stopWait();
            }
        });
    }
    else if (ReportName == "PrivateCommodityWise") {
        $("#divCommodityPrivateGird").hide();
        $("#OdivCommodityPrivateGird").html("Data is loading...");
        $("#tblCommodityPrivateGird").empty();
        $("#PrivateCommodity").text($("#drpCommodities_Private option:selected").text());
        $("#CommodityPrivateGird").css("display", "block");
        $("#OdivCommodityPrivateGird").show();
        $.ajax({
            url: "/ApmcDetail/GetArrivalPriceInfoByPrivateCommodityWise?commodityCode=" + CommoditiesId + "&apmcCode=" + ArrivalId,
            type: "GET",
            contentType: false,
            success: function (response) {
                if (response.length > 0 && response != "No record found!") {
                    if (response != null) {
                        $("#CommodityPrivateGird").addClass("active in");
                        $("#OdivCommodityPrivateGird").html();
                        $("#OdivCommodityPrivateGird").hide();
                        $("#tblCommodityPrivateGird").append(response);
                        $("#divCommodityPrivateGird").show();
                    }
                }
                else {
                    $("#OdivCommodityPrivateGird").html("<b>No Record found.</b>");
                    $("#tblCommodityPrivateGird").append(null);
                    $("#divCommodityPrivateGird").show();
                }
            },
            error: function (er) {
                $("#OdivCommodityPrivateGird").hide();
                kcs_Message.stopWait();
            }
        });
    }
    else if (ReportName == "PrivateMarketWise") {
        $("#divPrivateMarketGird").hide();
        $("#OdivPrivateMarketGird").html("Data is loading...");
        $("#tblPrivateMarketGird").empty();
        $("#Private_Market").text($("#drpPrivateMarket option:selected").text());
        $("#PrivateMarketGird").css("display", "block");
        $("#OdivPrivateMarketGird").show();
        $.ajax({
            url: "/ApmcDetail/GetArrivalPriceInfoByPrivateMarketWise?commodityCode=" + CommoditiesId + "&apmcCode=" + ArrivalId,
            type: "GET",
            contentType: false,
            success: function (response) {
                if (response.length > 0 && response != "No record found!") {
                    if (response != null) {
                        $("#PrivateMarketGird").addClass("active in");
                        $("#OdivPrivateMarketGird").html();
                        $("#OdivPrivateMarketGird").hide();
                        $("#tblPrivateMarketGird").append(response);
                        $("#divPrivateMarketGird").show();
                    }
                }
                else {
                    $("#OdivPrivateMarketGird").html("<b>No Record found.</b>");
                    $("#divPrivateMarketGird").show();
                    $("#tblPrivateMarketGird").append(null);
                }
            },
            error: function (er) {
                $("#OdivPrivateMarketGird").hide();
                kcs_Message.stopWait();
            }
        });
    }
    else {
        if (CommoditiesId != null) {
            $("#divCommodity").hide();
            $("#OdivCommodity").html("Data is loading...");
            $("#tblCommodity").empty();
            $("#APMCCommodity").text($("#drpCommodities option:selected").text());
            $("#CommodityGird").css("display", "block");
            $("#OdivCommodity").show();
        }
        else {
            $("#divAPMC").hide();
            $("#OdivAPMC").html("Data is loading...");
            $("#tblAPMC").empty();
            $("#APMCsAPMC").text($("#drpArrival option:selected").text());
            $("#ArrivalGird").css("display", "block");
            $("#divAPMC").show();
        }

        $.ajax({
            url: "/ApmcDetail/DataGridBind?commodityCode=" + CommoditiesId + "&apmcCode=" + ArrivalId,
            type: "GET",
            contentType: false,
            success: function (response) {
                if (CommoditiesId != null) {
                    if (response.length > 0 && response != "No record found!") {
                        if (response != null) {
                            $("#OdivCommodity").html();
                            $("#OdivCommodity").hide();
                            $("#tblCommodity").append(response);
                            $("#divCommodity").show();
                        }
                    }
                    else {
                        $("#OdivCommodity").html("<b>No Record found.</b>");
                        $("#tblCommodity").append(null);
                        $("#divCommodity").show();
                    }
                }
                else {
                    if (response.length > 0 && response != "No record found!") {
                        if (response != null) {
                            $("#OdivAPMC").html();
                            $("#OdivAPMC").hide();
                            $("#tblAPMC").append(response);
                            $("#divAPMC").show();
                        }
                    }
                    else {
                        $("#OdivAPMC").html("<b>No Record found.</b>");
                        $("#tblAPMC").append(null);
                        $("#divAPMC").show();
                    }
                }
            },
            error: function (er) {
                kcs_Message.stopWait();
            }
        });
    }
}

function bindDatacommodity(Data) {
    var str = "";
    for (var i = 0; i < Data.length; i++) {
        var Marketdate = Data[i].Date.split(' ')[0];
        var date = Marketdate.split('-');
        str += "<tr><td colspan=8>" + date[2] + '/' + date[1] + '/' + date[0] + " </td></tr>"
        for (var j = 0; j < Data[i].Data.length; j++) {
            str += "<tr><td>" + ((Language == "E") ? (Data[i].Data[j].ApmcNameE) : (Data[i].Data[j].ApmcNameM)) + "</td>" +
                "<td>" + ((Language == "E") ? (Data[i].Data[j].VarietyE) : (Data[i].Data[j].VarietyM)) + "</td>" +
                "<td>" + ((Language == "E") ? (Data[i].Data[j].UnitE) : (Data[i].Data[j].UnitM)) + "</td>" +
                "<td>" + Math.round(Data[i].Data[j].Quantity) + "</td>" +
                "<td>" + Math.round(Data[i].Data[j].Lrate) + "</td>" +
                "<td>" + Math.round(Data[i].Data[j].Hrate) + "</td>" +
                "<td>" + Math.round(Data[i].Data[j].Mrate) + "</td></tr>";
        }
    }
    $("#tblCommodity").empty();
    $("#tblCommodity").append(str);

}

function bindDataArrival(Data) {
    var str = "";
    Language = $("#hdnLanguage").val() != null ? $("#hdnLanguage").val() : "E";
    for (var i = 0; i < Data.length; i++) {
        var Marketdate = Data[i].Date.split(' ')[0];
        var date = Marketdate.split('-');
        str += "<tr><td colspan=8>" + date[2] + '/' + date[1] + '/' + date[0] + " </td></tr>"
        for (var j = 0; j < Data[i].Data.length; j++) {
            str += "<tr><td>" + ((Language == "E") ? (Data[i].Data[j].CommodityNameE) : (Data[i].Data[j].CommodityNameM)) + "</td>" +
                "<td>" + ((Language == "E") ? (Data[i].Data[j].VarietyE) : (Data[i].Data[j].VarietyM)) + "</td>" +
                "<td>" + ((Language == "E") ? (Data[i].Data[j].UnitE) : (Data[i].Data[j].UnitM)) + "</td>" +
                "<td>" + Math.round(Data[i].Data[j].Quantity) + "</td>" +
                "<td>" + Math.round(Data[i].Data[j].Lrate) + "</td>" +
                "<td>" + Math.round(Data[i].Data[j].Hrate) + "</td>" +
                "<td>" + Math.round(Data[i].Data[j].Mrate) + "</td></tr>";
        }
    }
    $("#tblAPMC").empty();
    $("#tblAPMC").append(str);
}

$("#idEducation").click(function () {
    //window.location = "http://eapmc.msambp.com/";
     window.location = "https://www.enam.gov.in/web/";

});