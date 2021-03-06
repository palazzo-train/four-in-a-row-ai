import gym
import numpy as np
from gym import spaces
import itertools as it
import random
from ..utils.logger import logger


class SuperNpcAgent():
    def __init__(self, button_color, child_agent ):
        self.button_color = button_color
        self.child_agent = child_agent
    

    def act(self, state):

        if self.child_agent is not None:
            action = self.child_agent.act(state)
        else:
            #### random
            board = state
            action = np.random.choice(np.where(board[0, :] == 0)[0])
        return action

class RandomNpcAgent():
    def act(self, state):

        #### random
        board = state
        action = np.random.choice(np.where(board[0, :] == 0)[0])
        return action


class FourInARowEnv(gym.Env):
    '''

        board = 6 x7 
        bottom = -1 (red) , 1 (green) , 0 (nothing) 
        player is red


        state = ( self.board.copy() , act_row, act_col )
    '''
    DONE_CONTINUE = 0 
    DONE_PLAYER_WIN = 1
    DONE_PLAYER_WRONG_MOVE = 2
    DONE_NPC_WIN = 3
    DONE_NPC_WRONG_MOVE = 4
    DONE_DRAW_GAME = 5

    REWARD_SCALER_PLAYED = True
    REWARD_SCALER_SPACE = False

    ##### this reward table only works for 7x6 board. 
        ###  The offsets and normalize_factor need to be retuned (recal) for other board size and discount factor
    NORMALIZE_FACTOR = 95
    REWARD_TABLE = {
        ### reward , done
        DONE_CONTINUE : [ 0 , REWARD_SCALER_PLAYED  , 0,  False],    # more played, longer step, higher reward
        DONE_PLAYER_WIN : [ 3 , REWARD_SCALER_SPACE , 0.0001,  True] ,   # more space = quick win, higher reward
        DONE_PLAYER_WRONG_MOVE : [ -0.1, REWARD_SCALER_SPACE , -100 , True] ,    # more space = quick wrong move,  higher neg reward
        DONE_NPC_WIN : [ -1 , REWARD_SCALER_SPACE , -3, True],     # more space = quick loss, higher neg reward
        DONE_DRAW_GAME : [ -0.02 , REWARD_SCALER_PLAYED  , -1 ,  True],
        DONE_NPC_WRONG_MOVE : [ +1.0 , REWARD_SCALER_SPACE , 0 , True]        # only in agent testing
    }
    '''
            'continue' : [ 0 , 'played' , 0,  False],    # more played, longer step, higher reward
            'player_win' : [ 3 , 'space', 0.0001,  True] ,   # more space = quick win, higher reward
            'player_wrong_move' : [ -0.1, 'space' , -100 , True] ,    # more space = quick wrong move,  higher neg reward
            'npc_win' : [ -1 , 'space', -3, True],     # more space = quick loss, higher neg reward
            'no_space' : [ -0.02 , 'played' , -1 ,  True],
            'npc_wrong_move' : [ +1.0 , 'space' , 0 , True]        # only in agent testing
            '''

    def __init__(self, npc_agent=None, test_agent=False):
        self.b_width = 7
        self.b_height = 6
        self.in_row_count = 4
        self.max_placed_button = (self.b_height * self.b_width)

        self.action_space = spaces.Discrete(7)
        self.observation_space = None

        self.test_agent = test_agent

        ## player is the agent or anyone play against the env
        self.player_button = -1
        self.npc_button = 1  # npc is the one who play for the env, giving response to player

        if npc_agent is None:
            self.npc_agent = RandomNpcAgent()
        else:
            self.npc_agent = npc_agent

        ####
        #
        # render paramter
        #
        self.cell_size = 40

        self.reset()

    def commit_move(self, new_board, new_avail_row):
        self.board = new_board.copy()
        self.avail_row = new_avail_row.copy()
        self.placed_button += 1

    def finish_step(self, scenario):

        done = False if scenario == FourInARowEnv.DONE_CONTINUE else True
        num_played_button = np.count_nonzero( self.board )
        num_space = self.max_placed_button - num_played_button 


        base_reward = FourInARowEnv.REWARD_TABLE[scenario][0]
        scaling_type = FourInARowEnv.REWARD_TABLE[scenario][1]
        offset = FourInARowEnv.REWARD_TABLE[scenario][2]
        done = FourInARowEnv.REWARD_TABLE[scenario][3]

        if scaling_type == FourInARowEnv.REWARD_SCALER_SPACE :
            scaling = num_space
        else :
            ### scaling_type == FourInARowEnv.REWARD_SCALER_PLAYED
            scaling = num_played_button

        reward = ( base_reward * scaling + offset ) / FourInARowEnv.NORMALIZE_FACTOR

        state = self.board.copy()

        return state, reward, done, scenario 




    def player_step(self,action):
        act_col = action
        done = False

        ### play move
        done, act_row, act_col, new_board, new_avail_row = FourInARowEnv.test_move(act_col, 
                    self.player_button, self.avail_row, self.board, self.b_width, self.b_height, self.in_row_count)

        self.commit_move(new_board, new_avail_row)

        # player wrong move
        if act_row == -1:  # wrong move
            return True,  FourInARowEnv.DONE_PLAYER_WRONG_MOVE 

        # player won
        if done:
            return True , FourInARowEnv.DONE_PLAYER_WIN

        ## check no space
        if self.placed_button >= self.max_placed_button:
            return True,  FourInARowEnv.DONE_DRAW_GAME 

        return False , ''


    def npc_find_easy_loss(self):

        for player_action in range(self.b_width):
            ## pretend player acton
            done, act_row, act_col, new_board, new_avail_row = FourInARowEnv.test_move(player_action, 
                        self.player_button , self.avail_row, self.board, self.b_width, self.b_height, self.in_row_count)
            
            if act_row == -1:  # wrong move
                continue

            # check win condition
            if done:
                ## player will win, npc should move here to defend
                return True, player_action

        return False, None

    def npc_find_easy_win(self):

        for npc_action in range(self.b_width):
            # trial move npc button
            done, act_row, act_col, new_board, new_avail_row = FourInARowEnv.test_move(npc_action, 
                        self.npc_button , self.avail_row, self.board, self.b_width, self.b_height, self.in_row_count)
            
            if act_row == -1:  # wrong move
                continue

            # check win condition
            if done:
                ## win
                return True, npc_action

        return False, None

    def npc_step(self):
        ### npc response

        if self.test_agent :
            npc_action = self.npc_agent.act(self.board)
        else:
            #### before asking npc agent, check easy win and loss move first
            found , npc_action = self.npc_find_easy_win()
            if not found:
                # no easy win move. check easy loss move 
                found , npc_action = self.npc_find_easy_loss()

                if not found:
                    # ask npc agent
                    npc_action = self.npc_agent.act(self.board)


        ## test the move
        done, act_row, act_col, new_board, new_avail_row = FourInARowEnv.test_move(npc_action, 
                    self.npc_button , self.avail_row, self.board, self.b_width, self.b_height, self.in_row_count)

        # wrong move by npc ,state no change
        if act_row == -1:  # wrong move
            if not self.test_agent:
                # the npc agen made wrong move. fallback to a random and move again
                npc_action = np.random.choice(np.where(self.board[0, :] == 0)[0])

                done, act_row, act_col, new_board, new_avail_row = FourInARowEnv.test_move(npc_action, 
                            self.npc_button , self.avail_row, self.board, self.b_width, self.b_height, self.in_row_count)
            else:
                #npc wrong move
                self.commit_move(new_board, new_avail_row)
                return True, FourInARowEnv.DONE_NPC_WRONG_MOVE


        self.commit_move(new_board, new_avail_row)

        #check is npc won
        if done:
            return True, FourInARowEnv.DONE_NPC_WIN 

        ## check no space
        ##
        ##  draw game
        if self.placed_button >= self.max_placed_button:
            return True, FourInARowEnv.DONE_DRAW_GAME 

        return False, FourInARowEnv.DONE_CONTINUE 

    def step(self, action):

        #### player action
        done, scenario = self.player_step(action)
        if done:
            return self.finish_step(scenario)

        # NPC response
        done, scenario = self.npc_step()
        if done:
            return self.finish_step(scenario)

        return self.finish_step( FourInARowEnv.DONE_CONTINUE )

    def reset(self):
        self.board = np.zeros((self.b_height, self.b_width)).astype(int)
        self.avail_row = np.ones(
            self.b_width).astype(int) * (self.b_height - 1)
        self.t = 0
        self.placed_button = 0

        ### random, sometime npc moves first
        if np.random.rand() >= 0.5:
            npc_action = self.npc_agent.act(self.board)
            done, act_row, act_col, new_board, new_avail_row = FourInARowEnv.test_move(npc_action, 
                                        self.npc_button, self.avail_row , self.board , self.b_width, self.b_height, self.in_row_count)
                                    
            # commit move
            self.board = new_board.copy()
            self.avail_row = new_avail_row.copy()

            self.placed_button += 1

        state = self.board.copy()
        return state

    ################
    #
    #  state transition
    #
    @staticmethod
    def test_move(act_col, act_button, cur_avail_row , cur_board , b_width, b_height, in_row_count):
        avail_row = cur_avail_row.copy()
        board = cur_board.copy()

        done = False
        # the column is full
        if avail_row[act_col] == -1:
            act_row = -1  # wrong move
            return done, act_row, act_col, board, avail_row

        board[avail_row[act_col], act_col] = act_button
        act_row = avail_row[act_col]
        avail_row[act_col] -= 1

        done = FourInARowEnv.check_win(act_button, act_row, act_col, board, b_width, b_height, in_row_count)
        return done, act_row, act_col, board, avail_row

    @staticmethod
    def check_win(act_button, act_row, act_col, board, b_width, b_height, in_row_count):
        # check horizonal
        for i in range(0, b_width - in_row_count + 1):
            if np.sum(board[act_row, i:i + in_row_count]) == (
                    act_button * in_row_count):
                return True

        # check vertical
        for i in range(0, b_height-in_row_count+1):
            if np.sum(board[i:i + in_row_count, act_col]) == (
                    act_button * in_row_count):
                return True

        # check diagonal
        # from bottom left to top right
        for i in range(in_row_count - 1, -1, -1):
            row0 = act_row + i
            col0 = act_col - i

            row1 = row0 - in_row_count + 1
            col1 = col0 + in_row_count - 1

            if (row1 >= 0) and (row0 < b_height) and (col0 >= 0) and ( col1 < b_width):
                total_b = 0
                for j in range(in_row_count):
                    irow = row0 - j
                    icol = col0 + j

                    total_b += board[irow, icol]

                if total_b == (act_button * in_row_count):
                    return True

        # check diagonal
        # from top left to bottom right
        for i in range(in_row_count - 1, -1, -1):
            row0 = act_row - i
            col0 = act_col - i

            row1 = row0 + in_row_count - 1
            col1 = col0 + in_row_count - 1

            if (row0 >= 0) and (row1 < b_height) and (col0 >= 0) and ( col1 < b_width):
                total_b = 0
                for j in range(in_row_count):
                    irow = row0 + j
                    icol = col0 + j

                    total_b += board[irow, icol]

                if total_b == (act_button * in_row_count):
                    return True

        return False

    #####################################
    #
    #  render
    #
    def render(self, mode):

        if mode == 'rgb_array':
            buffer = np.ones(
                (self.b_height * self.cell_size, self.b_width * self.cell_size,
                 3)).astype('uint8') * 255

            self.draw_grid(buffer)
            self.draw_button(buffer)
            #self.draw_chip(buffer)
            #self.draw_robot(buffer)
            #self.draw_goal(buffer)
            return buffer

        raise NotImplementedError

    def draw_button(self, buffer):
        for irow, icol in it.product(
                range(self.b_height), range(self.b_width)):
            start_x = icol * self.cell_size
            start_y = irow * self.cell_size

            if self.board[irow, icol] == self.player_button:
                for x, y in it.product(
                        range(start_x + 4, start_x + self.cell_size - 4),
                        range(start_y + 4, start_y + self.cell_size - 4)):
                    buffer[y, x] = [255, 0, 0]

            elif self.board[irow, icol] == self.npc_button:
                for x, y in it.product(
                        range(start_x + 4, start_x + self.cell_size - 4),
                        range(start_y + 4, start_y + self.cell_size - 4)):
                    buffer[y, x] = [0, 255, 0]

    def draw_grid(self, buffer):
        for irow, icol in it.product(
                range(self.b_height), range(self.b_width)):
            start_x = icol * self.cell_size
            start_y = irow * self.cell_size

            for x in range(start_x, start_x + self.cell_size):
                buffer[start_y, x] = [0, 0, 0]
                buffer[start_y + self.cell_size - 1, x] = [0, 0, 0]

            for y in range(start_y, start_y + self.cell_size):
                buffer[y, start_x] = [0, 0, 0]
                buffer[y, start_x + self.cell_size - 1] = [0, 0, 0]
