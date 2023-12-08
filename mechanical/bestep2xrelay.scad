   $fn=30;
module bolt(){
 
    translate([0,0,2])cylinder(d=5.5,h=20);
    translate([0,0,-18])cylinder(d=3.2,h=20);
}

module board(flood=false){
    difference(){
        union(){
            cube([80,47.5,1.6]); // pcb
            translate([50.6,7.8,1.6]) cube([19,15+1,15.5]); // relay 1
            translate([50.6,23.5,1.6]) cube([19,15,15.5]); // relay 1
            translate([71,8,1.6]) cube([10.3,15+1,14]); // conn relay
            translate([71,23.4,1.6]) cube([10.3,15.3,14]); // conn relay
            translate([0,3.5,1.6]) cube([8,40,10]); // conn left
            translate([18.5,1,1.6]) cube([7.6+1,5,10]); // jumper
            
            if(flood){
            translate([18.5,1,1.6]) cube([44,45,13]);
            translate([7,7.5,1.6]) cube([67,32,13]);
            
            for (i = [7.5,12.6,18.8,23.8,28.8,35,39.9] ){
            translate([4,i,0]) cylinder(d=3.2,h=20); // screw holes
            }
            for (i = [10.5,15.5,20.5,26,31.4,36.3] ){
            translate([77,i,0]) cylinder(d=3.2,h=20); // screw holes
            }
            translate([-10,-10,-10])cube([100,100,10]);
            
            }
            
            translate([15,4,1.6]) bolt();
            translate([69,4,1.6]) bolt();
            translate([15,43,1.6]) bolt();
            translate([69,43,1.6]) bolt();
            
            
        }


    }
}

module case(){
    difference(){
        rad = 3;
translate([rad,rad,rad-10]) minkowski(){
    cube([80-2*rad,47.5-2*rad,15.5-2*rad+10+1]);
    sphere(r=rad);
}

        board(true);
    }
    
}


case();




//board(true);
