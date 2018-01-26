import game
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--load")
    args = parser.parse_args()
    if args.load:
        game.load(args.load)
    else:
        game.new()
