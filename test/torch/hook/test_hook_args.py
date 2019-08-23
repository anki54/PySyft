from syft.frameworks.torch.hook import hook_args
from syft.generic import pointers
import torch as th
import torch.nn as nn
import torch.optim as optim
import numpy as np


def test_build_rule_syft_tensors_and_pointers():
    pointer = pointers.PointerTensor(
        id=1000, location="location", owner="owner", garbage_collect_data=False
    )
    result = hook_args.build_rule(([th.tensor([1, 2]), pointer], 42))
    assert result == ([1, 1], 0)


def test_build_rule_numpy():
    arr = np.array([2.0, 3.0, 4.0])
    result = hook_args.build_rule([arr, arr + 2, [2, 4, "string"]])
    assert result == [1, 1, [0, 0, 0]]


def test_backward_multiple_use(workers):
    """
    Test using backward() in different contexts (FL or Encrypted) within
    the same session.
    """
    big_hospital, small_hospital, crypto_provider = (
        workers["bob"],
        workers["alice"],
        workers["james"],
    )

    # A Toy Model
    class Net(nn.Module):
        def __init__(self):
            super(Net, self).__init__()
            self.fc = nn.Linear(2, 1)

        def forward(self, x):
            x = self.fc(x)
            return x

    def federated():
        # A Toy Dataset
        data = th.tensor([[0, 0], [0, 1], [1, 0], [1, 1.0]])
        target = th.tensor([[0], [0], [1], [1.0]])

        model = Net()

        # Training Logic
        opt = optim.SGD(params=model.parameters(), lr=0.1)

        data = data.send(big_hospital)
        target = target.send(big_hospital)

        # NEW) send model to correct worker
        model.send(data.location)

        # 1) erase previous gradients (if they exist)
        opt.zero_grad()

        # 2) make a prediction
        pred = model(data)

        # 3) calculate how much we missed
        loss = ((pred - target) ** 2).sum()

        # 4) figure out which weights caused us to miss
        loss.backward()

        # 5) change those weights
        opt.step()

    def encrypted():
        # A Toy Dataset
        data2 = th.tensor([[0, 0], [0, 1], [1, 0], [1, 1.0]])
        target2 = th.tensor([[0], [0], [1], [1.0]])

        model2 = Net()

        # We encode everything
        data2 = data2.fix_precision().share(
            big_hospital, small_hospital, crypto_provider=crypto_provider, requires_grad=True
        )
        target2 = target2.fix_precision().share(
            big_hospital, small_hospital, crypto_provider=crypto_provider, requires_grad=True
        )
        model2 = model2.fix_precision().share(
            big_hospital, small_hospital, crypto_provider=crypto_provider, requires_grad=True
        )

        opt2 = optim.SGD(params=model2.parameters(), lr=0.1).fix_precision()

        # 1) erase previous gradients (if they exist)
        opt2.zero_grad()

        # 2) make a prediction
        pred2 = model2(data2)

        # 3) calculate how much we missed
        loss2 = ((pred2 - target2) ** 2).sum()

        # 4) figure out which weights caused us to miss
        loss2.backward()

        # 5) change those weights
        opt2.step()

    federated()
    encrypted()
