$fn=60;
module screw(){
    cylinder(d=5.7,h=2.4);
    cylinder(d=3.2,h=9);
    cylinder(d=2.6,h=14.5);
}



module pcb(){
    translate([0,0,6])difference(){
        cylinder(d=26,h=1.7);
        translate([(21+4.8)/2,0,0])cylinder(d=4.8,h=1.7);
        translate([-(21+4.8)/2,0,0])cylinder(d=4.8,h=1.7);
    }
    translate([0,0,6])intersection(){
    translate([0,0,3.5/2])cube([18,22,3.5],center=true);
    cylinder(d=25,h=5);
    }
    translate([-6.4/2,0,-0.2])cylinder(d=4,h=6.2);
    translate([6.4/2,0,-0.2])cylinder(d=4,h=6.2);

}

module case(){
    translate([0,0,0])
    difference(){
        union(){
            difference(){
                union(){
                    cylinder(d=32,h=9); // outer contour
                    
                }

                translate([0,0,6])cylinder(d=26.5,h=5);// pcb space
                cylinder(d=12,h=10);
                
                hop = 60;
                for(i=[0:60:360]){
                    rotate([0,0,i+hop/2]) translate([10,0,3]) cylinder(d=5.1,h=3+10);
                    rotate([0,0,i+hop/2]) translate([10,0,0.45]) cylinder(d=5.3,h=3.5);
                }
                
                
                
            }
            translate([0,0,3])cube([1.5,12,6],center=true); // septum
            translate([ (21+4.8)/2,0,6])cylinder(d=4.5,h=1.6); // alignment pin
            translate([-(21+4.8)/2,0,6])cylinder(d=4.5,h=1.6); // alignment pin
        }
        translate([(21+4.8)/2,0,0])screw(); // screw hole
        translate([-(21+4.8)/2,0,0])screw(); // screw hole
        translate([0,0,6+1.7])cylinder(d=26.5+0.1,h=10); // lid space
        translate([0,0,11])rotate([90,0,0]) cylinder(d=6.1,h=20); // lid cable
        
        color("red") pcb();
    }

}

module lid(){
    difference(){
        union(){
            translate([0,0,9])cylinder(d=32,h=2); // outer contour lower
            translate([0,0,9+2])cylinder(d1=32,d2=29,h=3+1.2); // outer contour
            translate([0,0,6+1.7])cylinder(d=26.5,h=2); // lid inner ring
            translate([0,0,11])rotate([90,0,0]) cylinder(d=6,h=20);
        }
        innerh=5;
        translate([0,0,6+1.7])translate([0,0,innerh/2])cube([19,24,innerh],center=true); // inner room
        translate([(21+4.8)/2,0,0])screw(); // screw hole
        translate([-(21+4.8)/2,0,0])screw(); // screw hole
        translate([0,0,11])rotate([90,0,0]) cylinder(d=3.5,h=20); //cable
        
        color("red") pcb();
    }
}

module AAclyinder(){
    intersection(){
    cylinder(d=13,h=49.5);
    translate([0,2,50/2])cube([13,13,50],center=true);
    }
}

module distancering(){
    he= 6;
    translate([0,0,0])
    difference(){
        union(){
            difference(){
                union(){
                    cylinder(d=32,h=he); // outer contour
                    
                }

                cylinder(d=12,h=10);
                
                hop = 45;
                for(i=[0:hop:360]){
                    rotate([0,0,i+hop/2]) translate([11,0,3]) cylinder(d=5.1,h=3+10);
                    rotate([0,0,i+hop/2]) translate([11,0,0.45]) cylinder(d=5.3,h=3.5);
                }
      
            }
            //translate([0,0,he/2])cube([1.5,12,he],center=true); // septum
        }
        translate([5.5,0,3])rotate([0,15,0])cube([2.5,4,6.5],center=true);
        translate([11,0,5.5])cube([12,4,1],center=true);
    }

}

difference(){
union(){

case();
translate([50,0,0])lid();
translate([0,-50,0])distancering();
}
//rotate([0,0,38])cube(30);
}

//color("green")pcb();
translate([-50,0,0]) AAclyinder();



