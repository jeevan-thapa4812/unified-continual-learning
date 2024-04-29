# Copyright 2020-present, Pietro Buzzega, Matteo Boschini, Angelo Porrello, Davide Abati, Simone Calderara.
# All rights reserved.
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

import sys
from argparse import Namespace
from contextlib import suppress

import torch
import torch.nn as nn
from torch.optim import Adam, SGD

from utils.conf import get_device
from utils.magic import persistent_locals

with suppress(ImportError):
    import wandb

optimizer_dict = {
    'sgd': SGD,
    'adam': Adam
}


class ContinualModel(nn.Module):
    """
    Continual learning model.
    """
    NAME: str

    def __init__(self, backbone: nn.Module, loss: nn.Module,
                 args: Namespace, transform: nn.Module) -> None:
        super(ContinualModel, self).__init__()

        self.net = backbone
        self.loss = loss
        self.args = args
        self.transform = transform
        self.opt = optimizer_dict[args.opt](self.net.parameters(), lr=self.args.lr)  # opt created.
        self.device = get_device()

        if not self.NAME:
            raise NotImplementedError('Please specify the name and the compatibility of the model.')

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Computes a forward pass.
        :param x: batch of inputs
        :param task_label: some models require the task label
        :return: the result of the computation
        """
        return self.net(x)

    def meta_observe(self, *args, **kwargs):
        if 'wandb' in sys.modules and not self.args.nowand:
            pl = persistent_locals(self.observe)
            ret = pl(*args, **kwargs)
            self.autolog_wandb(pl.locals)
        else:
            ret = self.observe(*args, **kwargs)
        return ret

    def observe(self, cur_data, next_data) -> float:
        """
        Compute a training step over a given batch of examples.
        :param inputs: batch of examples
        :param labels: ground-truth labels
        :param kwargs: some methods could require additional parameters
        :return: the value of the loss function
        """
        raise NotImplementedError

    def autolog_wandb(self, locals):
        """
        All variables starting with "_wandb_" or "loss" in the observe function
        are automatically logged to wandb upon return if wandb is installed.
        """
        if not self.args.nowand and not self.args.debug_mode:
            wandb.log({k: (v.item() if isinstance(v, torch.Tensor) and v.dim() == 0 else v)
                       for k, v in locals.items() if k.startswith('_wandb_') or k.startswith('loss')})

    def save(self, save_path):
        """
        Checkpoint the model parameters on the local file system. 
        """
        torch.save(self.net.state_dict(), save_path)

    def load(self, load_path):
        """
        Load the model parameters on the local file system. 
        """
        self.net.load_state_dict(torch.load(load_path))
