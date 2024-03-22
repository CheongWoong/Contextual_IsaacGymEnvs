device_id=$1

test_seed=100

train_env_id=ContextualAnymalTrain

for train_seed in 0 1 2 3 4
do
    for env_id in ContextualAnymalTestEasy1 ContextualAnymalTestEasy2 ContextualAnymalTestEasy3 \
        ContextualAnymalTestEasy4 ContextualAnymalTestEasy5 ContextualAnymalTestEasy6 \
        ContextualAnymalTestEasy7 ContextualAnymalTestEasy8 ContextualAnymalTestEasy9 \
        ContextualAnymalTestHard1 ContextualAnymalTestHard2 ContextualAnymalTestHard3 ContextualAnymalTestHard4
    do
        run_name=$train_env_id"_osi_true_student"
        run_dir="runs/training/seed_"$train_seed"/"$run_name

        student_checkpoint_path=$run_dir"/checkpoints/99942400_phase1.pth"
        checkpoint_path=$run_dir"/checkpoints/99942400_phase2.pth"
        
        python -m src.v1.test_osi_true_student \
            --student_checkpoint_path $student_checkpoint_path \
            --checkpoint_path $checkpoint_path \
            --env_id $env_id \
            --device_id $device_id \
            --seed $test_seed
    done
done