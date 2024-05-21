import os
import os.path as osp

import glob
import torch
from devo.config import cfg

from devo_utils.load_utils import load_tumvie_traj, video_iterator, load_intrinsics_uw
from devo_utils.eval_utils import assert_eval_config, run_rgb
from devo_utils.eval_utils import log_results, write_raw_results, compute_median_results
from devo_utils.viz_utils import viz_flow_inference

H, W = 1024, 1024

@torch.no_grad()
def evaluate(config, args, net, train_step=None, datapath="", split_file=None,
             trials=1, stride=1, plot=False, save=False, return_figure=False, viz=False, camID=2, timing=False, viz_flow=False):
    dataset_name = "uw"
    assert camID == 0 or camID == 1
    assert H == 1024 and W == 1024, "Wrong resolution for TUMVIE"

    if config is None:
        config = cfg
        config.merge_from_file("config/default_rgb.yaml")
        config.__setattr__('camID', camID)

    scenes = open(split_file).read().split()

    results_dict_scene, figures = {}, {}
    all_results = []
    for i, scene in enumerate(scenes):
        print(f"Eval on {scene}")
        results_dict_scene[scene] = []

        for trial in range(trials):
            datapath_val = os.path.join(datapath, scene)
            traj_hf_path = osp.join(datapath_val, "mocap_data.txt")
            intrinsics = load_intrinsics_uw(datapath_val, camID=camID)
        
            # e2calibs = glob.glob(os.path.join(datapath_val, "e2calib_undistorted/"))
            # if len(e2calibs) == 0:
            #     print(f"Skipping {scene} - no E2VID-Recons")
            #     continue
            # else:
            #     e2calibs = e2calibs[0]    
            # scene_path = e2calibs
            # tss_file = os.path.join(e2calibs, "timestamps.txt")
            scene_path = datapath_val
            tss_file = os.path.join(datapath_val, "timestamps.txt")


            # run the slam system
            traj_est, tstamps, flowdata = run_rgb(scene_path, config, net, viz=viz,  \
                                        iterator=video_iterator(scene_path, tss_file=None, intrinsics=intrinsics, timing=timing, ext=".jpg", stride=stride), \
                                        timing=timing, H=H, W=W, viz_flow=viz_flow)
            
            tss_traj_us, traj_hf = load_tumvie_traj(traj_hf_path) 

            # do evaluation 
            data = (traj_hf, tss_traj_us, traj_est, tstamps)
            hyperparam = (train_step, net, dataset_name, scene, trial, cfg, args)
            all_results, results_dict_scene, figures, outfolder = log_results(data, hyperparam, all_results, results_dict_scene, figures, 
                                                                   plot=plot, save=save, return_figure=return_figure, stride=stride, camID_tumvie=camID,
                                                                   expname=args.expname)
        
            if viz_flow:
                viz_flow_inference(outfolder, flowdata)
        print(scene, sorted(results_dict_scene[scene]))

    # write output to file with timestamp
    write_raw_results(all_results, outfolder)
    results_dict = compute_median_results(results_dict_scene, all_results, dataset_name)
        
    if return_figure:
        return results_dict, figures
    return results_dict, None


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default="config/default_rgb.yaml") # for DPVO settings
    parser.add_argument('--datapath', default='', help='path to dataset directory')
    parser.add_argument('--weights', default="dpvo.pth")
    parser.add_argument('--val_split', type=str, default="splits/tumvie/tumvie_val.txt")
    parser.add_argument('--trials', type=int, default=5)
    parser.add_argument('--plot', action="store_true")
    parser.add_argument('--save_trajectory', action="store_true")
    parser.add_argument('--return_figs', action="store_true")
    parser.add_argument('--viz', action="store_true")
    parser.add_argument('--timing', action="store_true")
    parser.add_argument('--camID', type=int, default=0)
    parser.add_argument('--stride', type=int, default=1)
    parser.add_argument('--viz_flow', action="store_true")
    parser.add_argument('--expname', type=str, default="")

    args = parser.parse_args()
    assert_eval_config(args)

    cfg.merge_from_file(args.config)
    print("Running eval_uw_e2v.py with config...")
    print(cfg)

    torch.manual_seed(1234)

    val_results, val_figures = evaluate(cfg, args, args.weights, datapath=args.datapath, split_file=args.val_split, trials=args.trials, \
                       plot=args.plot, save=args.save_trajectory, return_figure=args.return_figs, viz=args.viz, camID=args.camID, \
                       timing=args.timing, stride=args.stride, viz_flow=args.viz_flow)
    
    print("val_results= \n")
    for k in val_results:
        print(k, val_results[k])

