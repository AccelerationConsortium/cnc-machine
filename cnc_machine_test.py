

from cnc_machine import CNC_Machine

'''Create your CNC Machine
Required Parameters:
    com = "COM3" or whatever com port you are using for your CNC
Optional parameters: 
    virtual=True/False run without an actual CNC machine on virtual
    baud rate=115200 by default
    locations_file='location_status.yaml' path to a YAML file with location definitions. Check out that file for examples. 
    X_LOW_BOUND=0
    X_HIGH_BOUND=270
    Y_LOW_BOUND=0
    Y_HIGH_BOUND=150
    Z_LOW_BOUND=-35
    Z_HIGH_BOUND=0
    These boundaries vary depending on your specific CNC machine and setup. The default parameters are for the small blue machine with the moving deck. Its important to set these so that you don't hit your limit switch. 
'''
m = CNC_Machine(com="COM3", virtual=False, locations_file='location_status.yaml') 

m.connect()                                                     # open persistent connection (optional)
m.home()                                                        # Home the CNC Machine
m.move_to_location("vial_rack", 1, safe=True, speed=2500)       # Move to vial rack position 1
m.move_to_point(100, 100, -30)                                  # Move to absolute point (100, 100, -30)
m.origin()                                                      # Move to 0,0,0
m.close()                                                    # Close persistent connection (only if opened)
