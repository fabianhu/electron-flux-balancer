// Box

%cube([300,250,150]);

// Netzteil HDR-15-12
translate([100,75,12])cube([17.5,90,54.5]);

module Hauptschalter()
{
    translate([0,-49/2,-45/2])cube([75,49,45]);
    translate([-35,(49-65)/2-49/2,(45-65)/2-45/2])cube([35,65,65]);
}

translate([0,200/2+50,100/2]) Hauptschalter();

translate([150,0,0]) cube([130,70,25]); // pi
translate([200,100,0]) cube([80,40,20]); // ti
translate([10,10,0]) cube([100,50,35]); // DO/DI
translate([10,70,0]) cube([80,45,25]); // Relay