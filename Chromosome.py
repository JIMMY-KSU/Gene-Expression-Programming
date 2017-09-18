from lib.anytree.node import Node
from lib.anytree.render import RenderTree

import matplotlib.pyplot as plt
import numpy as np
from random import randint
from warnings import warn


class Chromosome:

    # Functions and Terminals are shared by all chromosomes
    functions = dict()
    terminals = list()
    constants = dict()
    ephemeral_random_constants_range = (-1, 1)
    linking_function = None

    # length of head of chromosome
    num_genes = 3
    head_length = 6
    length = 39

    # list of real-valued tuples of the form (x, f(x))
    fitness_cases = []
    max_fitness = None


    def __init__(self, genes: list):

        # do not let chromosomes be defined without first defining their functions, terminals, and head length
        if not Chromosome.functions:
            raise ValueError("Chromosome class has no functions associated with it.")
        if len(Chromosome.terminals) == 0:
            raise ValueError("Chromosome class has no terminals associated with it.")
        if Chromosome.length is None:
            raise ValueError("Chromosome class has no length defined.")
        if Chromosome.head_length is None:
            raise ValueError("Chromosome class has no head length defined.")
        if Chromosome.linking_function is None and len(genes) > 1:
            raise ValueError("Multigenic chromosome defined with no linking function.")
        if len(genes) != Chromosome.num_genes:
            raise ValueError("Number of genes does not match excpected value in class level variable.")
        if "?" in Chromosome.terminals and Chromosome.ephemeral_random_constants_range is None:
            raise ValueError("Must define ephemeral random constants range if using ephemeral random constants.")

        # initialize chromosomes
        self.genes = genes
        self.trees = []
        self._values_ = {}
        self._fitness_ = None
        self.ephemeral_random_constants = list(np.random.uniform(*Chromosome.ephemeral_random_constants_range, size=Chromosome.length))


    # TODO - put informative error message when terminal_values doesn't have enough entries
    def evaluate(self, terminal_values: dict) -> float:
        """
        Returns the result of evaluating the given chromosome for specified fitness cases.

        :param terminal_values: dictionary mapping all present terminal symbols to real values
        :return: real valued result of evaluating the chromosome
        """

        # memoize value in case the chromosome was already evaluated
        value_fingerprint = tuple(sorted(terminal_values.items()))
        if value_fingerprint in self._values_:
            return self._values_[value_fingerprint]

        # build expression trees for each gene if not already built
        if len(self.trees) == 0:
            self.trees = [Chromosome.build_tree(gene) for gene in self.genes]

        # link expression trees if the chromosome is multigenic, otherwise use first tree
        if self.num_genes > 1:
            expression_tree = Chromosome.link(*self.trees)
        else:
            expression_tree = self.trees[0]

        erc_index = 0

        # recursive inorder tree traversal
        def inorder(start: Node) -> float:
            nonlocal terminal_values, erc_index
            if start.name in Chromosome.terminals:
                if start.name == "?":
                    erc_index += 1
                    return self.ephemeral_random_constants[erc_index - 1]
                if start.name in Chromosome.constants:
                    return Chromosome.constants[start.name]
                return int(start.name) if start.name.isdigit() else terminal_values[start.name]
            if start.name in Chromosome.functions:
                return Chromosome.functions[start.name]["f"](*[inorder(node) for node in start.children])

        try:
            self._values_[value_fingerprint] = inorder(expression_tree)
            if isinstance(self._values_[value_fingerprint], np.complex):
                raise TypeError
        # ZeroDivisionError if tree does something like x/(y-y), TypeError if the takes square root of a negative.
        except (ZeroDivisionError, TypeError):
            self._values_[value_fingerprint] = np.nan

        # noinspection PyTypeChecker
        return self._values_[value_fingerprint]


    def fitness(self) -> float:
        """
        Getter for fitness property to make sure we aren't grabbing uncalculated fitnesses

        :return: fitness of chromosome, or raise a warning and return 0 if fitness hasn't been calculated
        """
        if self._fitness_ is not None:
            return self._fitness_
        warn("Fitness of chromosome has not been properly calculated. Returning 0.")
        return 0


    def print_tree(self) -> None:
        """
        Use AnyTree to display a Chromosome's expression tree(s)

        :return: void
        """
        for t in range(len(self.trees)):
            print("Tree %d" % t)
            for pre, _, node in RenderTree(self.trees[t]):
                print("\t%s%s" % (pre, node.name))
        print(self.ephemeral_random_constants)

    def plot_solution(self, objective_function, x_min: float, x_max: float,
                      avg_fitnesses: list, best_fitnesses: list, variable_name: str) -> None:

        """
        Mostly unused, handy for plotting symbolic regression results though

        :param objective_function: ground truth function to plot
        :param x_min: minimum x value of plot
        :param x_max: maximum x value of plot
        :param avg_fitnesses: list of average fitness values by generation
        :param best_fitnesses: list of best fitness values by generation
        :return: void
        """

        if objective_function is not None:
            # set up subplots
            plt.subplots(1, 2, figsize=(16, 8))

            # Objective function vs Discovered function plot
            xs = np.linspace(x_min, x_max, 100)
            plt.subplot(1, 2, 1)
            plt.title("Discovered function vs. Objective function")
            plt.plot(xs, [objective_function(x) for x in xs],
                     linewidth=2, linestyle='dashed', color='black', label="Objective")
            plt.plot(xs, [self.evaluate({variable_name: x}) for x in xs],
                     linewidth=2, color='blue', label="Discovered")
            plt.legend(loc="upper left")

            # Fitness over time plot
            plt.subplot(1, 2, 2)

            plt.title("Fitness by Generation")
            plt.plot(range(len(avg_fitnesses)), avg_fitnesses, label="Average")
            plt.plot(range(len(best_fitnesses)), best_fitnesses, label="Best")
            plt.legend(loc="upper left")
            plt.show()

        else:
            plt.subplots(1, 1, figsize=(8, 8))
            plt.title("Fitness by Generation")
            plt.plot(range(len(avg_fitnesses)), avg_fitnesses, label="Average")
            plt.plot(range(len(best_fitnesses)), best_fitnesses, label="Best")
            plt.legend(loc="upper left")
            plt.show()


    @staticmethod
    def build_tree(gene: str) -> Node:
        """
        Constructs an expression tree from a gene.

        :param gene: gene to turn into expression tree
        :return: anytree Node of the root of the tree
        """

        # shortcut to get the number of arguments to a function
        def args(f: str) -> int:
            return Chromosome.functions[f]["args"] if f in Chromosome.functions else 0

        # recursively build chromosome tree
        def grab_children(parent: Node, current_level = 1):
            nonlocal levels
            if current_level < len(levels):
                nargs = args(parent.name)
                for i in range(nargs):
                    current_node = Node(levels[current_level][i], parent=parent)
                    grab_children(parent=current_node, current_level=current_level + 1)
                    if current_level < len(levels) - 1:
                        levels[current_level + 1] = levels[current_level + 1][args(current_node.name):]

        # build each level of the tree
        levels = [gene[0]]
        index = 0
        while index < len(gene) and sum([args(f) for f in levels[-1]]) != 0:
            nargs = sum([args(f) for f in levels[-1]])
            levels.append(gene[index + 1: index + 1 + nargs])
            index += nargs

        # intialize tree and parse
        tree = Node(gene[0])
        grab_children(tree)
        return tree


    @staticmethod
    # TODO - verify recursive linking with non-commutative linking functions (e.g. -)
    def link(*args) -> Node:
        """
        Links two trees at their roots using the specified linking function.
        Linking function must take as many arguments as number of args provided.

        :param args: expression trees to link. Must be at least as many expression trees as linking function has arguments.
        :return: expression tree with tree1 and tree2 as subtrees
        """

        if Chromosome.linking_function not in Chromosome.functions:
            raise ValueError("Linking function is not defined in Chromosome.functions.")
        if not all([isinstance(arg, Node) for arg in args]):
            raise TypeError("Can only link expression trees.")

        nargs = Chromosome.functions[Chromosome.linking_function]["args"]

        def link_recursive(*args) -> Node:
            root = Node(Chromosome.linking_function)
            if len(args) == nargs:
                for tree in args:
                    tree.parent = root
                return root
            else:
                return link_recursive(link_recursive(*args[:nargs]), *args[nargs:])

        return link_recursive(*args)


    @staticmethod
    # TODO - calculate using numpy arrays for speed
    def absolute_fitness(M: float, *args) -> np.ndarray:
        """
        Calculate absolute fitness of an arbitrary number of Chromosomes.

        :param M: range of fitness function over domain
        :param args: any number of gene objects
        :return: list of fitnesses of corresponding chromosomes
        """
        fitnesses = []
        for chromosome in args:
            # memoize fitness values
            if chromosome._fitness_ is not None:
                fitnesses.append(chromosome._fitness_)
            else:
                fitness = 0
                for j in range(len(Chromosome.fitness_cases)):
                    C_ij = chromosome.evaluate(Chromosome.fitness_cases[j][0])
                    # assign any chromosome that divides by zero a fitness value of zero
                    if type(C_ij) == np.complex or np.isnan(C_ij) or np.isinf(C_ij) or np.isneginf(C_ij):
                        fitness = 0
                        break
                    T_j = Chromosome.fitness_cases[j][1]
                    fitness += M - abs(C_ij - T_j)
                chromosome._fitness_ = fitness
                fitnesses.append(fitness)
        return np.asarray(fitnesses)


    @staticmethod
    # TODO - calculate using numpy arrays for speed
    def relative_fitness(M: float, *args) -> np.ndarray:
        """
        Calculate relative fitness of an arbitrary number of genes.

        :param M: range of fitness function over domain
        :param args: any number of gene objects
        :return: list of fitnesses of corresponding genes
        """
        fitnesses = []
        for chromosome in args:
            # memoize fitness values
            if chromosome._fitness_ is not None:
                fitnesses.append(chromosome._fitness_)
            else:
                fitness = 0
                for j in range(len(Chromosome.fitness_cases)):
                    C_ij = chromosome.evaluate(Chromosome.fitness_cases[j][0])
                    T_j = Chromosome.fitness_cases[j][1]
                    fitness += M - 100*abs(C_ij / T_j - 1)
                chromosome._fitness_ = fitness
                fitnesses.append(fitness)
        return np.asarray(fitnesses)


    @staticmethod
    def inv_squared_error(*args) -> np.ndarray:
        """
        Classical 1/(1+(squared error) fitness value.

        :param args: list of chromosomes to calculate fitness of
        :return: ndarray of fitness values for each given chromosome
        """
        fitnesses = []
        for chromosome in args:
            # memoize fitness values
            if chromosome._fitness_ is not None:
                fitnesses.append(chromosome._fitness_)
            else:
                fitness = 0
                for j in range(len(Chromosome.fitness_cases)):
                    C_ij = chromosome.evaluate(Chromosome.fitness_cases[j][0])
                    if type(C_ij) == np.complex or np.isnan(C_ij) or np.isinf(C_ij) or np.isneginf(C_ij):
                        fitness = np.inf
                        break
                    T_j = Chromosome.fitness_cases[j][1]
                    fitness += (C_ij - T_j)**2
                chromosome._fitness_ = 1.0/(1+fitness)
                fitnesses.append(chromosome._fitness_)
        return np.asarray(fitnesses)


    @staticmethod
    def centralized_inv_squared_error(center: float, dimension: str, *args) -> np.ndarray:
        """
        Mostly unused, a fitness function that focuses on error near a given point.

        :param center: point around which the fitness values are more important
        :param dimension: which dimension of the fitness case to use, in the case of multivariate functions
        :param args: any chromosomes to calculate fitness of
        :return: ndarray of fitness values
        """
        fitnesses = []
        for chromosome in args:
            # memoize fitness values
            if chromosome._fitness_ is not None:
                fitnesses.append(chromosome._fitness_)
            else:
                fitness = 0
                for j in range(len(Chromosome.fitness_cases)):
                    C_ij = chromosome.evaluate(Chromosome.fitness_cases[j][0])
                    if type(C_ij) == np.complex or np.isnan(C_ij) or np.isinf(C_ij) or np.isneginf(C_ij):
                        fitness = np.inf
                        break
                    T_j = Chromosome.fitness_cases[j][1]
                    fitness += abs(C_ij - T_j)**(1/abs(Chromosome.fitness_cases[j][0][dimension] - center))
                chromosome._fitness_ = 1.0 / (1 + fitness)
                fitnesses.append(chromosome._fitness_)
        return np.asarray(fitnesses)


    @staticmethod
    def generate_random_gene() -> str:
        """
        Generates one random gene based on settings specified in Chromosome class.
        :return: string of valid characters
        """
        possible_chars = list(Chromosome.functions.keys()) + Chromosome.terminals
        head = "".join([possible_chars[randint(0, len(possible_chars) - 1)] for _ in range(Chromosome.head_length)])
        tail = "".join([Chromosome.terminals[randint(0, len(Chromosome.terminals) - 1)] for _ in range(Chromosome.length - Chromosome.head_length)])
        return head + tail


    @staticmethod
    def generate_random_individual() -> 'Chromosome':
        """
        Generates one random individual based on settings specified in Chromosome class.
        :return: new Chromosome
        """
        return Chromosome([Chromosome.generate_random_gene() for _ in range(Chromosome.num_genes)])
