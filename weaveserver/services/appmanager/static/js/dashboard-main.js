$(document).ready(function() {
    var statusRequest = $.ajax({
        url: "/api/status",
        dataType: "json"
    });

    $.when(statusRequest).then(function(statusResponse) {
        var smallCards = [
            {
                cardType: 'success',
                icon: {material: 'build'},
                title: 'Version',
                content: statusResponse.version,
                footer: []
            },
            {
                cardType: 'warning',
                icon: {material: 'dns'},
                title: 'Rules',
                content: statusResponse.rules + " rules active",
                footer: []
            },
            {
                cardType: 'info',
                icon: {material: 'developer_board'},
                title: 'Plugins',
                content: statusResponse.plugins + " loaded",
                footer: []
            },
        ];

        var mediumCards = statusResponse.components;

        var smallCard = SmallCard();
        var mediumCard = MediumCard('.content .weave-medium-cards-row');

        $('.content .weave-small-cards-row').html($.map(smallCards, smallCard.html).join(""));
        mediumCards.forEach(mediumCard.load);
    });
});