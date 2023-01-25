""" 
** Code for Reward Function D in the paper **

This script contains drone training code with Venilla Gradient Decent optimizer

Optimizer: 
    Adam optimiser
Reward funciton: 
    +1000 for reaching target
    -1 at every other timestep
    -480 * (diatance to next target)  Though last target is not reached by the end of
                                    3000 steps distance covered till that time is added as a 
                                    reward.
    
      

"""


import numpy as np
from flight_controller import FlightController
from drone import Drone
from typing import Tuple
import pygame
import pickle
from main import *
import os, datetime

class HeuristicController(FlightController):


    def __init__(self):
        """Creates a heuristic flight controller with some specified parameters

        """
        pass
        

    def get_max_simulation_steps(self):
            return 3000 # You can alter the amount of steps you want your program to run for here


    def get_thrusts(self, drone: Drone) -> Tuple[float, float]:
        """Takes a given drone object, containing information about its current state
        and calculates a pair of thrust values for the left and right propellers.

        Args:
            drone (Drone): The drone object containing the information about the drones state.

        Returns:
            Tuple[float, float]: A pair of floating point values which respectively represent the thrust of the left and right propellers, must be between 0 and 1 inclusive.
        """
        
        # self.ky = 1.0
        # self.kx = 0.5
        # self.abs_pitch_delta = 0.1
        # self.abs_thrust_delta = 0.3

        target_point = drone.get_next_target()
        
        dx = target_point[0] - drone.x
        dy = target_point[1] - drone.y
        
        self.dist_from_last_step = np.sqrt(dx ** 2 + dy ** 2 )

        thrust_adj = np.clip(dy * self.ky, -self.abs_thrust_delta, self.abs_thrust_delta)
        target_pitch = np.clip(dx * self.kx, -self.abs_pitch_delta, self.abs_pitch_delta)
        delta_pitch = target_pitch-drone.pitch

        thrust_left = np.clip(0.5 + thrust_adj + delta_pitch, 0.0, 1.0)
        thrust_right = np.clip(0.5 + thrust_adj - delta_pitch, 0.0, 1.0)

        # The default controller sets each propeller to a value of 0.5 0.5 to stay stationary.
        return (thrust_left, thrust_right)

    def train(self, save_path):
        """A self contained method designed to train parameters created in the initialiser.
        """
        
        
        epochs = 120
        alpha = 1e-3
        b1 = 0.9
        b2 = 0.999
        
        params = [1.0, 0.5, 0.1, 0.3]                
        grads = [0, 0, 0, 0]
        m = [0, 0, 0, 0]
        v = [0, 0, 0, 0]

        for n in range(epochs):
            
            ## Forward pass
            print(f"Epoch:{n+1}")
            
            #Calculating total return of the trajectory for current parameters
            #See the done navigation visually for every 20 epochs
            if n == 0 or (n+1) % 20 == 0:
                R1, hits, dist_left  = self.getReturn(params,True)
            else:
                R1, hits, dist_left  = self.getReturn(params,False)
            
                        
            ## Back propagation / Estimating gradients
            #Using numerical approximation method           
                        
            for i in range(len(params)):
                #print(f" -- Finding Grad for parameter {i+1}")
                delta = 0.0001
                p1 = params[i]
                p2 = p1 + delta
                params_changed = params.copy()
                params_changed[i] = p2
                
                
                R2,_,_ = self.getReturn(params_changed, False)
                #Calclate the gradient
                dR = (R2-R1)/(p2-p1)
                grads[i] = dR
                #print(f"   - Reward is: {R2} Grad is: {dR}")
                
            ## Log the data before updating params
            data = {'epoch':n+1, 'params':params, 'grads':grads, 'reward': R1, 'hits': hits, 'dist_left':dist_left}            
            self.logWeights(n+1, data, save_path)
            print(f" > Reward: {R1}, Hits: {hits}, dist left: {dist_left}, params {params}, Grads: {grads}")
            
            ## Update parameters
            for i in range(len(params)):
                m[i] = b1 * m[i] + (1-b1) * grads[i]
                v[i] = b2 * v[i] + (1-b2) * grads[i] ** 2
                mt_cap = m[i]/(1-b1)
                vt_cap = v[i]/(1-b2)
                params[i] = params[i] + alpha * mt_cap/(np.sqrt(vt_cap)+1e-8)
                
                
          
    def getReturn(self, params, show_drone):
        """      

        Parameters
        ----------
        params : List
            List of parameters, potentially, changed parameters.
        show_drone : Boolean
            This tells wether to show or not the drone interaction with environment 
            with changed parameters as part of gradient descent.

        Returns
        -------
        return_ : int
            total return of the trajectory generated by following new parameters.

        """        
        
        self.ky = params[0]
        self.kx = params[1]
        self.abs_pitch_delta = params[2]
        self.abs_thrust_delta = params[3]
        return_ = 0
        target_hits = 0
        
        
        # Initialise pygame
        pygame.init()
        clock = pygame.time.Clock()

        # Load the relevant graphics into pygame
        drone_img = pygame.image.load('graphics/drone_small.png')
        background_img = pygame.image.load('graphics/background.png')
        target_img = pygame.image.load('graphics/target.png')
    

        # Create the screen
        SCREEN_WIDTH = 720
        SCREEN_HEIGHT = 480
        screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))    
        delta_time = self.get_time_interval()           
           
            
        # create a new drone simulation
        drone = self.init_drone()
        # 3) run simulation
        for t in range(self.get_max_simulation_steps()):
            drone.set_thrust(self.get_thrusts(drone))
            drone.step_simulation(self.get_time_interval())
            
            if show_drone:
                # Refresh the background
                screen.blit(background_img, (0,0))
                # Draw the current drone on the screen
                draw_drone(screen, drone, drone_img)
                # Draw the next target on the screen
                draw_target(drone.get_next_target(), screen, target_img)
            
                # Actually displays the final frame on the screen
                pygame.display.flip()
            
                # Makes sure that the simulation runs at a target 60FPS
                clock.tick(60)
                
            ## Calculate reward at this time step
            if drone.has_reached_target_last_update:                    
                return_ += 1000
                target_hits += 1
                
            else:
                ## Every time step is a negative reward
                return_ -= 1          
        
        ## At the end unfinished target left over distance is also added 
        # to return , smaller is better.
        # Multiplying with 480 to rescal to actual screen resolution , also 
        # to make gradients sufficiently large.
        dist_left = self.findDistance(drone) * 480        
        return_ -= dist_left           
            
        return return_, target_hits, dist_left
        
    def logWeights(self, epoch, data, save_path):
        """    
        This function is called after every epoch to save the complete 
        training data to the disk which helps later to plot and inspect the training.

        Parameters
        ----------
        epoch : int
            current epoch in the training.
        data : dictionary
            All the parameters data along with return generated with the parameters.
        save_path : string
            Directory and file path to save.

        Returns
        -------
        None.

        """         
        file_name = 'params_epoch{}.pkl'.format(epoch)
        file_path = os.path.join(save_path, file_name)        
        with open(file_path,'wb') as file:
            pickle.dump(data, file)
        
    def findDistance(self, drone: Drone):
        """
        Finds and returns euclidean distance between drone's current position and
        next target position.

        Parameters
        ----------
        drone : Drone
            Drone object which given state of the drone.

        Returns
        -------
        TYPE : Int
            Returns the euclidean distance from the drone's current position 
            to next target.

        """        
        target_point = drone.get_next_target()
        
        dx = target_point[0] - drone.x
        dy = target_point[1] - drone.y
        
        return np.sqrt(dx ** 2 + dy ** 2 )

    def load(self):
        """Load the parameters of this flight controller from disk.
        """
        try:
            parameter_array = np.load('heuristic_controller_parameters.npy')
            self.ky = parameter_array[0]
            self.kx = parameter_array[1]
            self.abs_pitch_delta = parameter_array[2]
            self.abs_thrust_delta = parameter_array[3]
        except:
            print("Could not load parameters, sticking with default parameters.")

    def save(self):
        """Save the parameters of this flight controller to disk.
        """
        parameter_array = np.array([self.ky, self.kx, self.abs_pitch_delta, self.abs_thrust_delta])
        np.save('heuristic_controller_parameters.npy', parameter_array)
        
        
if __name__ == "__main__":
    
    controller = HeuristicController()
    
    ## Making directory to log the training data
    newdir = os.path.join(os.getcwd(),"weights","run_"+datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))
    os.makedirs(newdir)
    
    ## Update read me text
    readme_text = """ Reward function with every step negative reward, positive for reaching the 
    target, left over distance of unfinished target also added to return. Opimizer changed to Adam  """
    with open(newdir+'/readme.txt', 'w') as f:
        f.write(readme_text)
        
    controller.train(newdir)