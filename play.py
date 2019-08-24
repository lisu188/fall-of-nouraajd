import game
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--load")
    parser.add_argument("--map")
    parser.add_argument("--player")
    args = parser.parse_args()
    if args.load:
        game.load(args.load)
    else:
        game.new(args.map, args.player)
