import models.resnet as RN
import models.resnet_ap as RNAP
import models.convnet as CN
import models.densenet_cifar as DN
from efficientnet_pytorch import EfficientNet
from misc.augment import DiffAug
from torchvision import datasets, transforms
from data import MEANS, STDS
import os
from data import transform_imagenet, transform_cifar, transform_svhn, transform_mnist, transform_fashion
from data import TensorDataset, ImageFolder, save_img, ImageFolder_mtt
from data import ClassDataLoader, ClassMemDataLoader, MultiEpochsDataLoader
from misc import utils
import torch
import numpy as np
from torch.utils.data import Dataset

import sys
sys.path.append('../')
from dataSolu.cifarm import CIFAR10m,CIFAR100m
from dataSolu.cifarn import CIFAR10n,CIFAR100n,CIFAR100n_coarse
from dataSolu.utils_noise import noisify


def define_model(args, nclass, logger=None, size=None):
    """Define neural network models
    """
    if size == None:
        size = args.size

    if args.net_type == 'resnet':
        model = RN.ResNet(args.dataset,
                          args.depth,
                          nclass,
                          norm_type=args.norm_type,
                          size=size,
                          nch=args.nch)
    elif args.net_type == 'resnet_ap':
        model = RNAP.ResNetAP(args.dataset,
                              args.depth,
                              nclass,
                              width=args.width,
                              norm_type=args.norm_type,
                              size=size,
                              nch=args.nch)
    elif args.net_type == 'efficient':
        model = EfficientNet.from_name('efficientnet-b0', num_classes=nclass)
    elif args.net_type == 'densenet':
        model = DN.densenet_cifar(nclass)
    elif args.net_type == 'convnet':
        width = int(128 * args.width)
        model = CN.ConvNet(nclass,
                           net_norm=args.norm_type,
                           net_depth=args.depth,
                           net_width=width,
                           channel=args.nch,
                           im_size=(args.size, args.size))
    else:
        raise Exception('unknown network architecture: {}'.format(args.net_type))

    if logger is not None:
        logger(f"=> creating model {args.net_type}-{args.depth}, norm: {args.norm_type}")
        # logger('# model parameters: {:.1f}M'.format(
        #     sum([p.data.nelement() for p in model.parameters()]) / 10**6))

    return model


class NoisyImageFolder(Dataset):
    def __init__(self, images, labels, transform=None):
        self.images = images
        self.labels = labels

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):
        img = self.images[idx]
        label = self.labels[idx]

        return img, label


def load_resized_data(args):
    """Load original training data (fixed spatial size and without augmentation) for condensation
    """

    if args.dataset == 'cifar10':
        normalize = transforms.Normalize(mean=MEANS['cifar10'], std=STDS['cifar10'])
        transform_test = transforms.Compose([transforms.ToTensor(), normalize])
        if args.is_annot == True:
            train_dataset = CIFAR10n(args.data_dir, train=True, transform=transforms.ToTensor(), download=True, noise_type=args.noise_type, noise_path = args.noise_path, is_human= args.is_human)
            val_dataset = CIFAR10n(args.data_dir, train=False, transform=transform_test, noise_type=args.noise_type, noise_path = args.noise_path, is_human= args.is_human)
        else:
            train_dataset = CIFAR10m(args.data_dir, train=True, transform=transforms.ToTensor(), download=True, noise_type=args.noise_type, noise_rate=args.noise_rate)
            val_dataset = CIFAR10m(args.data_dir, train=False, transform=transform_test, noise_type=args.noise_type, noise_rate=args.noise_rate)
        train_dataset.nclass = 10
        
    elif args.dataset == 'cifar100':
        normalize = transforms.Normalize(mean=MEANS['cifar100'], std=STDS['cifar100'])
        transform_test = transforms.Compose([transforms.ToTensor(), normalize])
        if args.is_annot == True:
            if args.is_coarse == True:
                train_dataset = CIFAR100n_coarse(args.data_dir, train=True, transform=transforms.ToTensor(), download=True, noise_type=args.noise_type, noise_path = args.noise_path, is_human= args.is_human)
                val_dataset = CIFAR100n_coarse(args.data_dir, train=False, transform=transform_test, noise_type=args.noise_type, noise_path = args.noise_path, is_human= args.is_human)
                train_dataset.nclass = 20
            else:
                train_dataset = CIFAR100n(args.data_dir, train=True, transform=transforms.ToTensor(), download=True, noise_type=args.noise_type, noise_path = args.noise_path, is_human= args.is_human)
                val_dataset = CIFAR100n(args.data_dir, train=False, transform=transform_test, noise_type=args.noise_type, noise_path = args.noise_path, is_human= args.is_human)
                train_dataset.nclass = 100
        else:
            train_dataset = CIFAR100m(args.data_dir,
                                            train=True,
                                            transform=transforms.ToTensor(),
                                            download=True,
                                            noise_type=args.noise_type,
                                            noise_rate=args.noise_rate)
            val_dataset = CIFAR100m(args.data_dir, train=False, transform=transform_test, noise_type=args.noise_type, noise_rate=args.noise_rate)
            train_dataset.nclass = 100
 
    elif args.dataset == 'svhn':
        train_dataset = datasets.SVHN(os.path.join(args.data_dir, 'SVHN'),
                                      split='train',
                                      transform=transforms.ToTensor())
        train_dataset.targets = train_dataset.labels

        normalize = transforms.Normalize(mean=MEANS['svhn'], std=STDS['svhn'])
        transform_test = transforms.Compose([transforms.ToTensor(), normalize])

        val_dataset = datasets.SVHN(os.path.join(args.data_dir, 'SVHN'),
                                    split='test',
                                    transform=transform_test)
        train_dataset.nclass = 10

    elif args.dataset == 'mnist':
        train_dataset = datasets.MNIST(args.data_dir, train=True, transform=transforms.ToTensor())

        normalize = transforms.Normalize(mean=MEANS['mnist'], std=STDS['mnist'])
        transform_test = transforms.Compose([transforms.ToTensor(), normalize])

        val_dataset = datasets.MNIST(args.data_dir, train=False, transform=transform_test)
        train_dataset.nclass = 10

    elif args.dataset == 'fashion':
        train_dataset = datasets.FashionMNIST(args.data_dir,
                                              train=True,
                                              transform=transforms.ToTensor())

        normalize = transforms.Normalize(mean=MEANS['fashion'], std=STDS['fashion'])
        transform_test = transforms.Compose([transforms.ToTensor(), normalize])

        val_dataset = datasets.FashionMNIST(args.data_dir, train=False, transform=transform_test)
        train_dataset.nclass = 10


    elif args.dataset == 'tinyimagenet':
        normalize = transforms.Normalize(mean=MEANS['tinyimagenet'], std=STDS['tinyimagenet'])
        transform_test = transforms.Compose([transforms.ToTensor(), normalize])

        train_dataset = datasets.ImageFolder(os.path.join(args.data_dir, "train"), transform=transforms.ToTensor()) # no augmentation
        val_dataset = datasets.ImageFolder(os.path.join(args.data_dir, "val"), transform=transform_test)
    
        # add noise
        if args.noise_type != 'clean':
            images = []
            labels = []
            
            for img, label in train_dataset:  
                images.append(img)
                labels.append(label)
                
            train_labels = np.asarray([[label] for label in labels])
            train_noisy_labels, actual_noise_rate = noisify(dataset='Tiny', train_labels=train_labels, noise_type=args.noise_type, noise_rate=args.noise_rate, random_state=0, nb_classes=200)
            targets_tmp = [i[0] for i in train_noisy_labels]
            print('over all noise rate is ', actual_noise_rate)
            train_noisy_labels = np.squeeze(train_noisy_labels)
            noisy_dst_train = NoisyImageFolder(images, train_noisy_labels)    
            noisy_dst_train.targets = targets_tmp
            train_dataset = noisy_dst_train
        train_dataset.nclass = 200

    elif args.dataset in ['imagenette', 'imagewoof', 'imagemeow', 'imagesquawk', 'imagefruit', 'imageyellow']:
        traindir = os.path.join(args.imagenet_dir, 'train')
        valdir = os.path.join(args.imagenet_dir, 'val')

        # We preprocess images to the fixed size (default: 128)
        resize = transforms.Compose([
            transforms.Resize(args.size),
            transforms.CenterCrop(args.size),
            transforms.PILToTensor()
        ])

        if args.load_memory:  # uint8
            transform = None
            load_transform = resize
        else:
            transform = transforms.Compose([resize, transforms.ConvertImageDtype(torch.float)])
            load_transform = None

        _, test_transform = transform_imagenet(size=args.size)
        train_dataset = ImageFolder_mtt(traindir,
                                        transform=transform,
                                        type=args.dataset,
                                        load_memory=args.load_memory,
                                        load_transform=load_transform)
        val_dataset = ImageFolder_mtt(valdir,
                                      test_transform,
                                            type=args.dataset,
                                            load_memory=False)





    elif args.dataset == 'imagenet':
        traindir = os.path.join(args.imagenet_dir, 'train')
        valdir = os.path.join(args.imagenet_dir, 'val')

        # We preprocess images to the fixed size (default: 224)
        resize = transforms.Compose([
            transforms.Resize(args.size),
            transforms.CenterCrop(args.size),
            transforms.PILToTensor()
        ])

        if args.load_memory:  # uint8
            transform = None
            load_transform = resize
        else:
            transform = transforms.Compose([resize, transforms.ConvertImageDtype(torch.float)])
            load_transform = None

        _, test_transform = transform_imagenet(size=args.size)
        train_dataset = ImageFolder(traindir,
                                    transform=transform,
                                    nclass=args.nclass,
                                    phase=args.phase,
                                    seed=args.dseed,
                                    load_memory=args.load_memory,
                                    load_transform=load_transform)
        val_dataset = ImageFolder(valdir,
                                  test_transform,
                                  nclass=args.nclass,
                                  phase=args.phase,
                                  seed=args.dseed,
                                  load_memory=False)

    val_loader = MultiEpochsDataLoader(val_dataset,
                                       batch_size=args.batch_size // 2,
                                       shuffle=False,
                                       persistent_workers=True,
                                       num_workers=4)

    assert train_dataset[0][0].shape[-1] == val_dataset[0][0].shape[-1]  # width check

    return train_dataset, val_loader


def remove_aug(augtype, remove_aug):
    aug_list = []
    for aug in augtype.split("_"):
        if aug not in remove_aug.split("_"):
            aug_list.append(aug)

    return "_".join(aug_list)


# def diffaug(args, device='cuda'):
#     """Differentiable augmentation for condensation
#     """
#     aug_type = args.aug_type
#     normalize = utils.Normalize(mean=MEANS[args.dataset], std=STDS[args.dataset], device=device)
#     print("Augmentataion Matching: ", aug_type)
#     augment = DiffAug(strategy=aug_type, batch=True)
#     aug_batch = transforms.Compose([normalize, augment])

#     return aug_batch

def diffaug(args, device='cuda'):
    """Differentiable augmentation for condensation
    """
    aug_type = args.aug_type
    normalize = utils.Normalize(mean=MEANS[args.dataset], std=STDS[args.dataset], device=device)
    print("Augmentataion Matching: ", aug_type)
    augment = DiffAug(strategy=aug_type, batch=True)
    aug_batch = transforms.Compose([normalize, augment])

    if args.mixup == 'cut':
        aug_type = remove_aug(aug_type, 'cutout')
    print("Augmentataion Net update: ", aug_type)
    augment_rand = DiffAug(strategy=aug_type, batch=False)
    aug_rand = transforms.Compose([normalize, augment_rand])

    return aug_batch, aug_rand




def normaug(args, device='cuda'):
    """Differentiable augmentation for condensation
    """
    normalize = utils.Normalize(mean=MEANS[args.dataset], std=STDS[args.dataset], device=device)
    norm_aug = transforms.Compose([normalize])
    return norm_aug







































