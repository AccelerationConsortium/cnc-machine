<h1> CNC MACHINE CODE </h1>
Owen Melville 2025-08-27 
Feel free to use this repo without credit

<h2> Overall description </h2>
This package can be used to control Genmitsu CNC machines. This is useful for accelerated discovery because you can put your tools onto the CNC machine. All you need is to install the packages in requirements.txt then you can import cnc_machine.py and use its methods to intuitively and seemlessly move the cnc machine with whatever scientific tools you want to incorporate. 

<h3>Basic Functions:</h3>

- Home CNC machine
  
- Move to absolute points (x,y,z)
  
- Move to locations defined in a structured way (Eg move to Vial Position 0)
  
- Handles all gcode and CNC communication so you don't have to
  
- Makes sure you don't move the CNC machine to a position it can't go

 <h3> Description of Methods:</h3>
 
  - home(): homes the robot and parks it at the origin
  
  - origin(): moves the robot to the origin
    
  - move_to_point(x,y,z) move to point (x,y,z)
    
  - move_to_location(location, location_index) move to location position location_index
    
  - open() and close() are optional commands to open and close a persistent connection to the CNC machine

<h3>Locations:</h3>

- There are two example locations, a location and a location array in the location_status.yaml file in the directory

- vial_rack: #Array-location 

  - num_x: 2 #Rows
    
  - num_y: 4 #Columns

  - x_origin: 166.5 #move the cnc machine with the needle attached, and find the position
    
  - y_origin: 125
    
  - z_origin: 0
    
  - x_offset: 36 #Measure with caliper
    
  - y_offset: -36 #MEasure with caliper
 
<img width="1580" height="1190" alt="image" src="https://github.com/user-attachments/assets/2022a495-b026-4f38-a9e6-7f2ad14fdd05" />

  
<h3>Advice on Integration with Scientific Instruments</h3>

- Create a separate python file for each tool (camera, force sensor, syringe pump, etc.)
  
- Create an instrument class that imports cnc_machine along with the python files for each tool (eg fraction_collector.py)
  
- In your instrument class make methods that intuitively describe the general actions of your instrument (eg dispense_fraction)
  
- Make your workflows in seperate python files or Jupyter notebook files that create an instance of your instrument class
  
- This will make your workflows as clean and simple as possible while hard to mess up!
