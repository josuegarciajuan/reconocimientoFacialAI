from collections import deque

 

class fifo:

    def __init__(self):

        self.lista=deque([])

 

    def apilar(self, elemento):

        """

        Metodo para añadir elementos a la pila

        Puede recibir un valor o una lista de valores

        @param string|list elemento

        @return self

        """

        if type(elemento)==list:

            self.lista.extend(elemento)

        else:

            self.lista.append(elemento)

        return self

 

    def desapilar(self):

        """

        Metodo para quitar el primer elemento de la lista

        Si no hay elementos en la lista devuelve False

        @return string|False

        """

        try:

            return self.lista.popleft()

        except AttributeError:

            return False

 

    def vaciar(self):

        """

        Metodo para vaciar la lista

        @return self

        """

        self.lista=[]

        return self

 

    def tamano(self):

        """

        Metodo para obtener el tamaño de la pila

        @return integer

        """

        return len(self.lista)

 

    def obtenerPila(self):

        """

        Metodo que devuelve la pila

        @return list

        """

        return list(self.lista)