$fn=60;

module NT18B07(){
difference(){
cube([60,37,1.6]);

translate([0+2.5,13.4+2.4/2,-0.1])cylinder(d=2.4,h=2);
translate([55+2.5,13.4+2.4/2,-0.1])cylinder(d=2.4,h=2);
translate([55+2.5,37-2.4,-0.1])cylinder(d=2.4,h=2);
}

translate([0,2.5,1.6])cube([60,6,8]);
translate([50,16.5,1.6])cube([8,15,10]);
translate([3,27,1.6])cube([8,10,10]);
translate([0,17,1.6])cube([14.5,9,10]);
}

module holes(){

translate([0,0,0]) cylinder(d=3.2, h=5);
translate([55.5,0,0]) cylinder(d=3.2, h=5);
translate([55.5,28,0]) cylinder(d=3.2, h=5);
translate([0,28,0]) cylinder(d=3.2, h=5);
//translate([55.5,28/2,0]) cylinder(d=3.2, h=5);
//translate([0,28/2,0]) cylinder(d=3.2, h=5);

translate([0,0,2]) cylinder(d=5.5, h=5);
translate([55.5,0,2]) cylinder(d=5.5, h=5);
translate([55.5,28,2]) cylinder(d=5.5, h=5);
translate([0,28,2]) cylinder(d=5.5, h=5);
//translate([55.5,28/2,2]) cylinder(d=5.5, h=5);
//translate([0,28/2,2]) cylinder(d=5.5, h=5);
}

module carrier(){
    % translate([0,0,5]) NT18B07();
    difference(){
        union(){
            translate([-0.5,-1,0])cube([60+1,37+1,2]);

            translate([0+2.5,13.4+2.4/2,1])cylinder(d=5,h=4);
            translate([55+2.5,13.4+2.4/2,1])cylinder(d=5,h=4);
            translate([55+2.5,37-2.4,1])cylinder(d=5,h=4);
            
            translate([0,0,1])cube([60,2.5,4]); // support
            
            translate([0+2,32+3,1])cylinder(d=4,h=4);
            
        }
        translate([0+2.5,13.4+2.4/2,-0.1])cylinder(d=1.6,h=6);
        translate([55+2.5,13.4+2.4/2,-0.1])cylinder(d=1.6,h=6);
        translate([55+2.5,37-2.4,-0.1])cylinder(d=1.6,h=6);
    
        translate([2.25,1.5,-0.10]) holes();
        
        hull(){
        translate([30-10,18,-1])cylinder(d=28,h=10);
        translate([30+10,18,-1])cylinder(d=28,h=10);
        }
        
    }
}

carrier();



