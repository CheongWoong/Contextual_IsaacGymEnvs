# reference: https://github.com/vwxyzjn/cleanrl/blob/master/cleanrl/ppo_continuous_action_isaacgym/ppo_continuous_action_isaacgym.py

# Copyright (c) 2018-2022, NVIDIA Corporation
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# docs and experiment results can be found at https://docs.cleanrl.dev/rl-algorithms/ppo/#ppo_continuous_action_isaacgympy
import os
import random
import time
from dataclasses import dataclass

import gym
import isaacgym  # noqa
import isaacgymenvs
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import tyro
from torch.distributions.normal import Normal
from torch.utils.tensorboard import SummaryWriter


@dataclass
class Args:
    exp_name: str = os.path.basename(__file__)[: -len(".py")]
    """the name of this experiment"""
    seed: int = 0
    """seed of the experiment"""
    torch_deterministic: bool = True
    """if toggled, `torch.backends.cudnn.deterministic=False`"""
    cuda: bool = True
    """if toggled, cuda will be enabled by default"""
    track: bool = False
    """if toggled, this experiment will be tracked with Weights and Biases"""
    wandb_project_name: str = "cleanRL"
    """the wandb's project name"""
    wandb_entity: str = None
    """the entity (team) of wandb's project"""
    capture_video: bool = False
    """whether to capture videos of the agent performances (check out `videos` folder)"""

    # Algorithm specific arguments
    env_id: str = "Ant"
    """the id of the environment"""
    total_timesteps: int = 30000000
    """total timesteps of the experiments"""
    learning_rate: float = 0.0026
    """the learning rate of the optimizer"""
    num_envs: int = 4096
    """the number of parallel game environments"""
    num_steps: int = 16
    """the number of steps to run in each environment per policy rollout"""
    anneal_lr: bool = False
    """Toggle learning rate annealing for policy and value networks"""
    num_minibatches: int = 2
    """the number of mini-batches"""
    update_epochs: int = 4
    """the K epochs to update the policy"""
    max_grad_norm: float = 1
    """the maximum norm for the gradient clipping"""
    num_checkpoints: int = 10 # cwkang: added to save the model parameters
    """the number of checkpoints to save the model"""
    device_id: int = 7 # cwkang: set the gpu id
    """the gpu id"""

    len_history: int = 10
    # cwkang: Checkpoint path to load the exploration policy
    checkpoint_path: str = ""
    """the path to the checkpoint"""

    # to be filled in runtime
    batch_size: int = 0
    """the batch size (computed in runtime)"""
    minibatch_size: int = 0
    """the mini-batch size (computed in runtime)"""
    num_iterations: int = 0
    """the number of iterations (computed in runtime)"""
    

class RecordEpisodeStatisticsTorch(gym.Wrapper):
    def __init__(self, env, device):
        super().__init__(env)
        self.num_envs = getattr(env, "num_envs", 1)
        self.device = device
        self.episode_returns = None
        self.episode_lengths = None

    def reset(self, **kwargs):
        observations = super().reset(**kwargs)
        self.episode_returns = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.episode_lengths = torch.zeros(self.num_envs, dtype=torch.int32, device=self.device)
        self.returned_episode_returns = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.returned_episode_lengths = torch.zeros(self.num_envs, dtype=torch.int32, device=self.device)
        return observations

    def step(self, action):
        observations, rewards, dones, infos = super().step(action)
        self.episode_returns += rewards
        self.episode_lengths += 1
        self.returned_episode_returns[:] = self.episode_returns
        self.returned_episode_lengths[:] = self.episode_lengths
        self.episode_returns *= 1 - dones
        self.episode_lengths *= 1 - dones
        infos["r"] = self.returned_episode_returns
        infos["l"] = self.returned_episode_lengths
        return (
            observations,
            rewards,
            dones,
            infos,
        )


def layer_init(layer, std=np.sqrt(2), bias_const=0.0):
    torch.nn.init.orthogonal_(layer.weight, std)
    torch.nn.init.constant_(layer.bias, bias_const)
    return layer


NUM_SYS_PARAMS = 2 # cwkang: add input dim
class Agent(nn.Module):
    def __init__(self, envs):
        super().__init__()
        self.critic = nn.Sequential(
            layer_init(nn.Linear(np.array(envs.single_observation_space.shape).prod() + NUM_SYS_PARAMS, 256)), # cwkang: add input dim
            nn.Tanh(),
            layer_init(nn.Linear(256, 256)),
            nn.Tanh(),
            layer_init(nn.Linear(256, 1), std=1.0),
        )
        self.actor_mean = nn.Sequential(
            layer_init(nn.Linear(np.array(envs.single_observation_space.shape).prod() + NUM_SYS_PARAMS, 256)), # cwkang: add input dim
            nn.Tanh(),
            layer_init(nn.Linear(256, 256)),
            nn.Tanh(),
            layer_init(nn.Linear(256, np.prod(envs.single_action_space.shape)), std=0.01),
        )
        self.actor_logstd = nn.Parameter(torch.zeros(1, np.prod(envs.single_action_space.shape)))

    def get_value(self, x):
        return self.critic(x)

    def get_action_and_value(self, x, action=None):
        action_mean = self.actor_mean(x)
        action_logstd = self.actor_logstd.expand_as(action_mean)
        action_std = torch.exp(action_logstd)
        probs = Normal(action_mean, action_std)
        if action is None:
            action = probs.sample()
        return action, probs.log_prob(action).sum(1), probs.entropy().sum(1), self.critic(x)
    

class OSI(nn.Module):
    def __init__(self, envs, len_history):
        super().__init__()
        obs_dim = np.array(envs.single_observation_space.shape).prod()
        action_dim = np.prod(envs.single_action_space.shape)
        self.context_encoder = nn.Sequential(
            layer_init(nn.Linear((obs_dim+action_dim)*len_history - action_dim, 256)),
            nn.Tanh(),
            layer_init(nn.Linear(256, 128)),
            nn.Tanh(),
            layer_init(nn.Linear(128, 64)),
            nn.Tanh(),
            layer_init(nn.Linear(64, 10)),
            nn.Tanh()
        )
        self.estimator = nn.Sequential(
            layer_init(nn.Linear(10, 10)),
            nn.Tanh(),
            layer_init(nn.Linear(10, NUM_SYS_PARAMS)),
        )

    def forward(self, history):
        context = self.context_encoder(history)
        return self.estimator(context)
    
    def get_context(self, history):
        return self.context_encoder(history)


class ExtractObsWrapper(gym.ObservationWrapper):
    def observation(self, obs):
        return obs["obs"]


if __name__ == "__main__":
    args = tyro.cli(Args)
    args.batch_size = int(args.num_envs * args.num_steps)
    args.minibatch_size = int(args.batch_size // args.num_minibatches)
    args.num_iterations = args.total_timesteps // args.batch_size
    # run_name = f"{args.env_id}__{args.exp_name}__{args.seed}__{int(time.time())}"
    # run_name = f"idm_training/{args.env_id}__{args.exp_name}__{args.seed}__{time.strftime('%Y-%m-%d_%H:%M:%S', time.localtime(time.time()))}" # cwkang: use datetime format for readability
    run_name = f"osi_training/seed_{args.seed}/{args.env_id}"
    os.makedirs(f"runs/{run_name}/checkpoints", exist_ok=True) # cwkang: prepare the directory for saving the model parameters
    if args.track:
        import wandb

        wandb.init(
            project=args.wandb_project_name,
            entity=args.wandb_entity,
            sync_tensorboard=True,
            config=vars(args),
            name=run_name,
            monitor_gym=True,
            save_code=True,
        )
    writer = SummaryWriter(f"runs/{run_name}")
    writer.add_text(
        "hyperparameters",
        "|param|value|\n|-|-|\n%s" % ("\n".join([f"|{key}|{value}|" for key, value in vars(args).items()])),
    )

    # TRY NOT TO MODIFY: seeding
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.backends.cudnn.deterministic = args.torch_deterministic

    device = torch.device("cuda" if torch.cuda.is_available() and args.cuda else "cpu")
    
    # env setup
    envs = isaacgymenvs.make(
        seed=args.seed,
        task=args.env_id,
        num_envs=args.num_envs,
        sim_device=f"cuda:{args.device_id}" if torch.cuda.is_available() and args.cuda else "cpu",
        rl_device=f"cuda:{args.device_id}" if torch.cuda.is_available() and args.cuda else "cpu",
        graphics_device_id=0 if torch.cuda.is_available() and args.cuda else -1,
        headless=False if torch.cuda.is_available() and args.cuda else True,
        multi_gpu=False,
        virtual_screen_capture=args.capture_video,
        force_render=False,
    )
    envs = ExtractObsWrapper(envs)
    envs = RecordEpisodeStatisticsTorch(envs, device)
    envs.single_action_space = envs.action_space
    envs.single_observation_space = envs.observation_space
    assert isinstance(envs.single_action_space, gym.spaces.Box), "only continuous action space is supported"

    agent = Agent(envs).to(device)
    agent.load_state_dict(torch.load(f'{args.checkpoint_path}'))
    agent.eval()
    # optimizer = optim.Adam(agent.parameters(), lr=args.learning_rate, eps=1e-5)

    # cwkang: initialize the inverse dynamics model
    osi = OSI(envs, args.len_history).to(device)
    optimizer = optim.Adam(osi.parameters(), lr=args.learning_rate, eps=1e-5)
    mse_loss = nn.MSELoss()

    # ALGO Logic: Storage setup
    obs = torch.zeros((args.num_steps, args.num_envs) + envs.single_observation_space.shape, dtype=torch.float).to(device)
    actions = torch.zeros((args.num_steps, args.num_envs) + envs.single_action_space.shape, dtype=torch.float).to(device)
    dones = torch.zeros((args.num_steps, args.num_envs), dtype=torch.float).to(device)
    sys_param_weights = torch.zeros((args.num_steps, args.num_envs, 2), dtype=torch.float).to(device) # cwkang: add storage for system parameters

    # TRY NOT TO MODIFY: start the game
    global_step = 0
    start_time = time.time()
    next_obs = envs.reset()
    next_done = torch.zeros(args.num_envs, dtype=torch.float).to(device)
    sys_param_weight = envs.get_sys_param_weight() # cwkang: get system parameters

    for iteration in range(1, args.num_iterations + 1):
        # Annealing the rate if instructed to do so.
        if args.anneal_lr:
            frac = 1.0 - (iteration - 1.0) / args.num_iterations
            lrnow = frac * args.learning_rate
            optimizer.param_groups[0]["lr"] = lrnow

        for step in range(0, args.num_steps):
            global_step += args.num_envs
            obs[step] = next_obs
            dones[step] = next_done
            sys_param_weights[step] = sys_param_weight # cwkang: store system parameters

            # ALGO LOGIC: action logic
            with torch.no_grad():
                #######
                # action, logprob, _, value = agent.get_action_and_value(next_obs)

                # cwkang: use system parameters as additional input
                next_obs_with_sys_param = torch.cat((next_obs, sys_param_weight), dim=-1)
                action, logprob, _, value = agent.get_action_and_value(next_obs_with_sys_param)
                #######
            actions[step] = action

            # TRY NOT TO MODIFY: execute the game and log data.
            next_obs, _, next_done, info = envs.step(action)

        # flatten the batch
        b_obs = obs.reshape((-1,) + envs.single_observation_space.shape)
        b_actions = actions.reshape((-1,) + envs.single_action_space.shape)
        b_actions = torch.clamp(b_actions, -envs.clip_actions, envs.clip_actions) # cwkang: clip action for accurate prediction without noise
        b_dones = dones.reshape(-1)
        b_sys_param_weights = sys_param_weights.reshape((-1, NUM_SYS_PARAMS)) # cwkang: add system parameters

        # Optimizing the policy and value network
        clipfracs = []
        for epoch in range(args.update_epochs):
            b_inds = torch.randperm(args.batch_size-args.len_history, device=device) # cwkang: -len_history since the last states do not have next_obs
            for start in range(0, args.batch_size, args.minibatch_size):
                end = start + args.minibatch_size
                mb_inds = b_inds[start:end]

                # cwkang: prepare history input
                history_dones = b_dones[mb_inds].reshape((-1, 1))
                for i in range(1, args.len_history):
                    history_dones = torch.cat((history_dones, b_dones[mb_inds + i].reshape((-1, 1))), dim=-1)
                last_done_indices = (history_dones == 1).cumsum(dim=1).max(dim=1).indices
                timesteps = torch.arange(history_dones.size(1), device=device).expand_as(history_dones)
                history_input_mask = timesteps >= last_done_indices.unsqueeze(1)

                history_input_obs = b_obs[mb_inds]*history_input_mask[:,0:1]
                for i in range(1, args.len_history):
                    history_input_obs = torch.cat((history_input_obs, b_obs[mb_inds + i]*history_input_mask[:,i:i+1]), dim=-1)
                history_input_action = b_actions[mb_inds]*history_input_mask[:,0:1]
                for i in range(1, args.len_history-1):
                    history_input_action = torch.cat((history_input_action, b_actions[mb_inds + i]*history_input_mask[:,i:i+1]), dim=-1)
                history_input = torch.cat((history_input_obs, history_input_action), dim=-1)

                predicted_system_params = osi(history_input)
                # predicted_system_params *= 0
                # predicted_system_params += b_sys_param_weights.mean(0)[None,:]
                osi_label = b_sys_param_weights[mb_inds + args.len_history-1]
                
                osi_loss = torch.sqrt(mse_loss(predicted_system_params, osi_label) + 1e-8)

                optimizer.zero_grad()
                osi_loss.backward()
                nn.utils.clip_grad_norm_(osi.parameters(), args.max_grad_norm)
                optimizer.step()

        # TRY NOT TO MODIFY: record rewards for plotting purposes
        writer.add_scalar("charts/learning_rate", optimizer.param_groups[0]["lr"], global_step)
        writer.add_scalar("losses/osi_loss", osi_loss.item(), global_step)
        print("SPS:", int(global_step / (time.time() - start_time)))
        writer.add_scalar("charts/SPS", int(global_step / (time.time() - start_time)), global_step)

        # cwkang: save the model parameters
        if iteration % (args.num_iterations // args.num_checkpoints) == 0 or iteration == args.num_iterations:
            torch.save(osi.state_dict(), f"runs/{run_name}/checkpoints/{global_step}.pth")


    # envs.close()
    writer.close()