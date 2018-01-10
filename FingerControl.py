#William Yager
#Leap Python mouse controller POC
#This file is for pointer-finger-based control (--finger and default)


import math
import sys
from leap import Leap, Mouse
from MiscFunctions import *

SCREEN_W = 1920.0 # Big screen
SCREEN_H = 1080.0
# SCREEN_W = 1366.0 # Laptop
# SCREEN_H = 768.0
#PLANE_ORIGIN: mm, (x,y,z)
# PLANE_ORIGIN = Leap.Vector(0.0, 0.0, -270.0) # Big screen
# xOffset = 20.0
# yOffset = 50.0
# PLANE_ORIGIN = Leap.Vector(100.0, 50.0, -350.0) # Laptop

# class Manual_Intersect(): 

class Finger_Control_Listener(Leap.Listener):  #The Listener that we attach to the controller. This listener is for pointer finger movement

    def get_screen_info(self):
        print "Enter the distance between leap and screen (z-axis) in mm:"
        leap_screen_dist = float(raw_input())
        self.plane_origin = Leap.Vector(0.0, 0.0, -leap_screen_dist)

        print "If pointer is too far to the left or right, enter distance to offset on x-axis in mm:"
        answer = raw_input()
        if (answer == ''):
            self.x_offset = 0
        else:
            self.x_offset = float(answer)
        print "[x_offset = ", self.x_offset, "]"

        print "If pointer is too far up or down, enter distance to offset on y-axis in mm:"
        answer = raw_input()
        if (answer == ''):
            self.y_offset = 0
        else:
            self.y_offset = float(answer)
        print "[y_offset = ", self.x_offset, "]"

        print 'MD TODO make this stuf work smoothly, store settings in pickle, push upstream'
        print 'MD TODO checkout opentsps '

    def rayPlaneIntersect(self, rayorigin, in_raydirection, in_planenormal):  
        ''''' 
        @returns: Vector3, intersectionPoint-rayOrigin 
        '''  
        raydirection = in_raydirection.normalized  
        planenormal = in_planenormal.normalized  
        distanceToPlane = (rayorigin-self.plane_origin).dot(planenormal)  
        triangleHeight = raydirection.dot(-planenormal)  
        if not distanceToPlane:  
            return rayorigin-self.plane_origin  
        if not triangleHeight:  
            return None #ray is parallel to plane  
        return raydirection * distanceToPlane * (1.0/triangleHeight) 



    def __init__(self, mouse, smooth_aggressiveness=8, smooth_falloff=1.3):
        super(Finger_Control_Listener, self).__init__()  #Initialize like a normal listener
        #Initialize a bunch of stuff specific to this implementation
        self.screen = None
        self.screen_resolution = (0,0)
        self.cursor = mouse.absolute_cursor()  #The cursor object that lets us control mice cross-platform
        self.mouse_position_smoother = mouse_position_smoother(smooth_aggressiveness, smooth_falloff) #Keeps the cursor from fidgeting
        self.mouse_button_debouncer = debouncer(5)  #A signal debouncer that ensures a reliable, non-jumpy click
        self.most_recent_pointer_finger_id = None  #This holds the ID of the most recently used pointing finger, to prevent annoying switching
        self.manualIntersect = False

    def on_init(self, controller):
        if controller.located_screens.is_empty:
            print "Cannot find screen."
            print "This is an issue with the Leap SDK. As of 2013-11-15: \"The Screen Locator tool is not currently supported on any operating system\"."
            print "Switching into experimental manual mode..."
            self.manualIntersect = True
            self.get_screen_info()
            #sys.exit(0)
        else:
            print "Found a screen..."
            self.screen = controller.located_screens[0]
            self.screen_resolution = (self.screen.width_pixels, self.screen.height_pixels)

        print "Initialized"

    def on_connect(self, controller):
        print "Connected"

    def on_disconnect(self, controller):
        print "Disconnected"

    def on_exit(self, controller):
        print "Exited"

    def on_frame(self, controller):
        frame = controller.frame()  #Grab the latest 3D data
        if not frame.hands.is_empty:  #Make sure we have some hands to work with
            hand = frame.hands[0]  #The first hand
            if has_two_pointer_fingers(hand):  #Scroll mode
                self.do_scroll_stuff(hand)
            else:  #Mouse mode
                self.do_mouse_stuff(controller, hand)

    def do_scroll_stuff(self, hand):  #Take a hand and use it as a scroller
        fingers = hand.fingers  #The list of fingers on said hand
        if not fingers.is_empty:  #Make sure we have some fingers to work with
            sorted_fingers = sort_fingers_by_distance_from_screen(fingers)  #Prioritize fingers by distance from screen
            finger_velocity = sorted_fingers[0].tip_velocity  #Get the velocity of the forwardmost finger
            x_scroll = self.velocity_to_scroll_amount(finger_velocity.x)
            y_scroll = self.velocity_to_scroll_amount(finger_velocity.y)
            self.cursor.scroll(x_scroll, y_scroll)

    def velocity_to_scroll_amount(self, velocity):  #Converts a finger velocity to a scroll velocity
        #The following algorithm was designed to reflect what I think is a comfortable
        #Scrolling behavior.
        vel = velocity  #Save to a shorter variable
        vel = vel + math.copysign(300, vel)  #Add/subtract 300 to velocity
        vel = vel / 150
        vel = vel ** 3  #Cube vel
        vel = vel / 8
        vel = vel * -1  #Negate direction, depending on how you like to scroll
        return vel

    def do_mouse_stuff(self, controller, hand):  #Take a hand and use it as a mouse
        fingers = hand.fingers  #The list of fingers on said hand
        # pointer = controller.frame().tools.frontmost
        # if pointer.is_valid:

        if not fingers.is_empty:  #Make sure we have some fingers to work with
            pointer = self.select_pointer_finger(fingers)  #Determine which finger to use
        
            if (not self.manualIntersect):
                try:
                    intersection = self.screen.intersect(pointer, True)  #Where the finger projection intersects with the screen
                    if not math.isnan(intersection.x) and not math.isnan(intersection.y):  #If the finger intersects with the screen
                        x_coord = intersection.x * self.screen_resolution[0]  #x pixel of intersection
                        y_coord = (1.0 - intersection.y) * self.screen_resolution[1]  #y pixel of intersection
                        x_coord,y_coord = self.mouse_position_smoother.update((x_coord,y_coord)) #Smooth movement
                        self.cursor.move(x_coord,y_coord)  #Move the cursor
                        if has_thumb(hand):  #We've found a thumb!
                            self.mouse_button_debouncer.signal(True)  #We have detected a possible click. The debouncer ensures that we don't have click jitter
                        else:
                            self.mouse_button_debouncer.signal(False)  #Same idea as above (but opposite)

                        if self.cursor.left_button_pressed != self.mouse_button_debouncer.state:  #We need to push/unpush the cursor's button
                            self.cursor.set_left_button_pressed(self.mouse_button_debouncer.state)  #Set the cursor to click/not click
                except Exception as e:
                    print e
            else: #do manualIntersect
                # pointer properties: tip_position, direction, tip_velocity, touch_distance, touch_zone, stabilized_tip_position
            
                # Averaging as per leap website
                
                count = 0
                avgPos = Leap.Vector()
                avgDir = Leap.Vector()
                fingerToavgPos = controller.frame().fingers[0]
                AVG_OVER = 15
                for i in range(0,AVG_OVER):
                    fingerFromFrame = controller.frame(i).finger(fingerToavgPos.id)
                    if(fingerFromFrame.is_valid):
                        if (i==0):
                            invI = 50
                        else:
                            invI = 1
                        for j in range(invI):
                            avgPos += fingerFromFrame.stabilized_tip_position
                            avgDir += fingerFromFrame.direction
                            count += 1
                    avgPos /= count
                    avgDir /= count
                
                if (count == 0):
                    pointerPos = pointer.stabilized_tip_position
                    pointerDir = pointer.direction
                else:
                    pointerPos = avgPos
                    pointerDir = avgDir
            
            
                mm_to_pixels = 6
                
                in_planenormal = Leap.Vector(0.0, 0.0, 1.0)
                intersection = self.rayPlaneIntersect(pointerPos, pointerDir, in_planenormal) 

                if not math.isnan(intersection.x) and not math.isnan(intersection.y):  #If the finger intersects with the screen
                    x,y = intersection.x, intersection.y
                    y = -y
                    y += self.y_offset
                    x += self.x_offset
                    
                    x *= mm_to_pixels
                    y *= mm_to_pixels
                    
                    x += SCREEN_W/2
                    y += SCREEN_H/2     

                    # x,y = self.mouse_position_smoother.update((x,y)) #Smooth movement
                        
                    self.cursor.move(x,y)  #Move the cursor

    def select_pointer_finger(self, possible_fingers):  #Choose the best pointer finger
        sorted_fingers = sort_fingers_by_distance_from_screen(possible_fingers)  #Prioritize fingers by distance from screen
        if self.most_recent_pointer_finger_id != None:  #If we have a previous pointer finger in memory
             for finger in sorted_fingers:  #Look at all the fingers
                if finger.id == self.most_recent_pointer_finger_id:  #The previously used pointer finger is still in frame
                    return finger  #Keep using it
        #If we got this far, it means we don't have any previous pointer fingers OR we didn't find the most recently used pointer finger in the frame
        self.most_recent_pointer_finger_id = sorted_fingers[0].id  #This is the new pointer finger
        return sorted_fingers[0]
